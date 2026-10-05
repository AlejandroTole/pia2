
"""Carga y validación de la configuración de PIA 2.0 desde YAML.
 
Objetivo de diseño: que el usuario cambie símbolos y modo demo/real (y todo
lo operativo) SIN tocar código, editando solo config/config.yaml. Este loader
lee ese archivo, valida los valores y devuelve un PIAConfig tipado.
"""
 
from __future__ import annotations
 
import os
import warnings
from pathlib import Path
 
import yaml
 
from config.schema import (
    VALID_DAYS,
    VALID_ACCOUNT_TYPES,
    VALID_EXECUTIONS,
    VALID_MODES,
    VALID_TIMEFRAMES,
    AIConfig,
    CandlePolicyConfig,
    ConfluenceConfig,
    HistoricalConfig,
    IndicatorsConfig,
    LoopConfig,
    NewsConfig,
    ObservabilityConfig,
    PIAConfig,
    RiskConfig,
    ScheduleConfig,
    Session,
)
 
 
class ConfigError(Exception):
    """Error de configuración inválida o ausente."""
 
 
DEFAULT_CONFIG_PATH = "config/config.yaml"
 
 
def load_config(path: str | os.PathLike | None = None) -> PIAConfig:
    """Carga la configuración desde YAML y la valida.
 
    Si no se pasa ruta, usa config/config.yaml. Si ese archivo no existe pero
    sí existe config/config.example.yaml, lanza un error claro pidiendo copiarlo.
    """
    config_path = Path(path) if path else Path(DEFAULT_CONFIG_PATH)
 
    if not config_path.exists():
        example = config_path.parent / "config.example.yaml"
        if example.exists():
            raise ConfigError(
                f"No existe '{config_path}'. Copia '{example}' a '{config_path}' "
                "y ajusta tus valores."
            )
        raise ConfigError(f"No se encontró el archivo de configuración: {config_path}")
 
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
 
    if not isinstance(raw, dict):
        raise ConfigError("El archivo de configuración debe ser un mapa (clave: valor).")
 
    config = _build_config(raw)
    _validate(config)
    return config
 
 
def _build_config(raw: dict) -> PIAConfig:
    risk = RiskConfig(**_subset(raw.get("risk", {}), RiskConfig))
    indicators = IndicatorsConfig(**_subset(raw.get("indicators", {}), IndicatorsConfig))
    confluence = ConfluenceConfig(**_subset(raw.get("confluence", {}), ConfluenceConfig))
    candle_policy = CandlePolicyConfig(
        **_subset(raw.get("candle_policy", {}), CandlePolicyConfig)
    )
    news = NewsConfig(**_subset(raw.get("news", {}), NewsConfig))
    historical = HistoricalConfig(**_subset(raw.get("historical", {}), HistoricalConfig))
    ai = AIConfig(**_subset(raw.get("ai", {}), AIConfig))
    loop = LoopConfig(**_subset(raw.get("loop", {}), LoopConfig))
    observability = ObservabilityConfig(
        **_subset(raw.get("observability", {}), ObservabilityConfig)
    )
    schedule = _build_schedule(raw.get("schedule", {}))
 
    top = _subset(raw, PIAConfig, exclude={
        "risk", "indicators", "confluence", "candle_policy", "news", "historical", "ai", "loop", "observability", "schedule",
    })

    # Translate the v1 mode only when the new execution axis is absent.
    if "execution" not in raw:
        top["execution"] = "broker" if raw.get("mode") == "real" else "simulated"
 
    return PIAConfig(
        risk=risk,
        indicators=indicators,
        confluence=confluence,
        candle_policy=candle_policy,
        news=news,
        historical=historical,
        ai=ai,
        loop=loop,
        observability=observability,
        schedule=schedule,
        **top,
    )
 
 
def _build_schedule(raw: dict) -> ScheduleConfig:
    sessions_raw = raw.get("sessions", []) or []
    sessions: list[Session] = []
    for item in sessions_raw:
        if not isinstance(item, dict) or "start" not in item or "end" not in item:
            raise ConfigError("Cada 'session' debe tener 'start' y 'end' (HH:MM).")
        sessions.append(Session(start=str(item["start"]), end=str(item["end"])))
 
    kwargs = {}
    if "timezone" in raw:
        kwargs["timezone"] = raw["timezone"]
    if "trade_days" in raw:
        kwargs["trade_days"] = list(raw["trade_days"])
    if sessions:
        kwargs["sessions"] = sessions
 
    return ScheduleConfig(**kwargs)
 
 
def _subset(raw: dict, cls, exclude: set[str] | None = None) -> dict:
    """Toma solo las claves del dict que correspondan a campos de la dataclass.
 
    Ignora claves desconocidas para no romper por typos triviales, pero avisa.
    """
    exclude = exclude or set()
    valid_fields = set(cls.__dataclass_fields__.keys())
    unknown = []
    result = {}
    for key, value in raw.items():
        if key in exclude:
            continue
        if key in valid_fields:
            result[key] = value
        else:
            unknown.append(key)
    if unknown:
        warnings.warn(
            f"Claves de configuración no reconocidas ignoradas: {sorted(unknown)}",
            UserWarning,
            stacklevel=2,
        )
    return result
 
 
def _validate(config: PIAConfig) -> None:
    if config.mode not in VALID_MODES:
        raise ConfigError(f"'mode' debe ser uno de {VALID_MODES}, no '{config.mode}'.")
    if config.execution not in VALID_EXECUTIONS:
        raise ConfigError(
            f"'execution' debe ser uno de {VALID_EXECUTIONS}, no '{config.execution}'."
        )
    if config.account_type_required not in VALID_ACCOUNT_TYPES:
        raise ConfigError(
            "'account_type_required' debe ser 'demo' o 'live'."
        )
 
    if not config.symbols:
        raise ConfigError("Debes definir al menos un símbolo en 'symbols'.")
 
    if config.timeframe not in VALID_TIMEFRAMES:
        raise ConfigError(
            f"'timeframe' debe ser uno de {VALID_TIMEFRAMES}, no '{config.timeframe}'."
        )
    if config.entry_timeframe not in VALID_TIMEFRAMES:
        raise ConfigError(
            f"'entry_timeframe' debe ser uno de {VALID_TIMEFRAMES}, "
            f"no '{config.entry_timeframe}'."
        )
 
    r = config.risk
    if not 0 < r.risk_per_trade_pct <= 100:
        raise ConfigError("risk_per_trade_pct debe estar entre 0 y 100.")
    if r.max_margin_per_trade_usd <= 0:
        raise ConfigError("max_margin_per_trade_usd debe ser > 0.")
    if not 0 < r.max_daily_loss_pct <= 100:
        raise ConfigError("max_daily_loss_pct debe estar entre 0 y 100.")
    if not 0 < r.max_drawdown_pct <= 100:
        raise ConfigError("max_drawdown_pct debe estar entre 0 y 100.")
    if r.max_trades_per_day < 1:
        raise ConfigError("max_trades_per_day debe ser >= 1.")
    if r.max_open_positions < 1:
        raise ConfigError("max_open_positions debe ser >= 1.")
    if r.max_same_currency_exposure < 1:
        raise ConfigError("max_same_currency_exposure debe ser >= 1.")
    if r.cooldown_minutes_after_loss < 0:
        raise ConfigError("cooldown_minutes_after_loss debe ser >= 0.")
    if r.breakeven_trigger_atr < 0:
        raise ConfigError("breakeven_trigger_atr debe ser >= 0.")
    if r.max_holding_minutes < 0:
        raise ConfigError("max_holding_minutes debe ser >= 0.")
 
    c = config.confluence
    if not 0 <= c.decision_engine_weight <= 1:
        raise ConfigError("decision_engine_weight debe estar entre 0 y 1.")

    cp = config.candle_policy
    if not 0 <= cp.min_strength <= 100:
        raise ConfigError("candle_policy.min_strength debe estar entre 0 y 100.")
    if not 0 <= cp.conflict_penalty <= 100:
        raise ConfigError("candle_policy.conflict_penalty debe estar entre 0 y 100.")
    if not 0 <= cp.aligned_boost <= 100:
        raise ConfigError("candle_policy.aligned_boost debe estar entre 0 y 100.")
    if not 0 <= cp.veto_strength <= 100:
        raise ConfigError("candle_policy.veto_strength debe estar entre 0 y 100.")

    n = config.news
    if n.refresh_minutes < 1:
        raise ConfigError("news.refresh_minutes debe ser >= 1.")
    if n.historical_lookback_days < 1:
        raise ConfigError("news.historical_lookback_days debe ser >= 1.")
    if n.calendar_scan_days < 1:
        raise ConfigError("news.calendar_scan_days debe ser >= 1.")
    if n.calendar_scan_days > n.historical_lookback_days:
        raise ConfigError(
            "news.calendar_scan_days no puede ser mayor que news.historical_lookback_days."
        )
    if not n.reaction_windows_minutes:
        raise ConfigError("news.reaction_windows_minutes no puede estar vacío.")
    if any(v <= 0 for v in n.reaction_windows_minutes):
        raise ConfigError("news.reaction_windows_minutes debe tener minutos > 0.")
    if n.min_pattern_events < 1:
        raise ConfigError("news.min_pattern_events debe ser >= 1.")
    if n.block_high_before_minutes < 0 or n.block_high_after_minutes < 0:
        raise ConfigError("news bloqueos high deben ser >= 0.")
    if n.block_medium_before_minutes < 0 or n.block_medium_after_minutes < 0:
        raise ConfigError("news bloqueos medium deben ser >= 0.")
    if not 0 <= n.confidence_boost_aligned <= 100:
        raise ConfigError("news.confidence_boost_aligned debe estar entre 0 y 100.")
    if not 0 <= n.confidence_penalty_conflict <= 100:
        raise ConfigError("news.confidence_penalty_conflict debe estar entre 0 y 100.")

    o = config.observability
    if o.log_level not in {"QUIET", "INFO", "DEBUG"}:
        raise ConfigError("observability.log_level debe ser QUIET, INFO o DEBUG.")
    if o.heartbeat_seconds < 1:
        raise ConfigError("observability.heartbeat_seconds debe ser >= 1.")
 
    for day in config.schedule.trade_days:
        if day not in VALID_DAYS:
            raise ConfigError(f"Día inválido en trade_days: '{day}'. Válidos: {VALID_DAYS}.")
 
    for session in config.schedule.sessions:
        _validate_hhmm(session.start)
        _validate_hhmm(session.end)
 
 
def _validate_hhmm(value: str) -> None:
    parts = value.split(":")
    if len(parts) != 2:
        raise ConfigError(f"Hora inválida '{value}', formato esperado HH:MM.")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        raise ConfigError(f"Hora inválida '{value}', formato esperado HH:MM.")
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ConfigError(f"Hora fuera de rango '{value}'.")