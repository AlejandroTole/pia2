"""Esquema tipado de la configuración de PIA 2.0.
 
Estas dataclasses son la "fuente de verdad" de qué campos existen y de qué
tipo son. El loader (loader.py) construye estos objetos a partir del YAML y
valida los valores, de modo que el resto del código trabaja con objetos
tipados en vez de diccionarios sueltos.
"""
 
from __future__ import annotations
 
from dataclasses import dataclass, field
 
 
VALID_MODES = ("demo", "real")
VALID_EXECUTIONS = ("simulated", "broker")
VALID_ACCOUNT_TYPES = ("demo", "live")
VALID_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
VALID_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
 
 
@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 0.5
    max_margin_per_trade_usd: float = 500.0
    # Campo legado (v1): se mantiene para no romper configs antiguas.
    max_position_size_usd: float | None = None
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0
    max_trades_per_day: int = 8
    max_open_positions: int = 1
    max_same_currency_exposure: int = 1
    min_confidence: float = 60.0
    max_spread_points: float | dict[str, float] = 30.0
    block_symbol_stacking: bool = True
    cooldown_minutes_after_loss: int = 120
 
 
@dataclass
class Session:
    start: str  # "HH:MM"
    end: str    # "HH:MM"
 
 
@dataclass
class ScheduleConfig:
    timezone: str = "America/Toronto"
    sessions: list[Session] = field(default_factory=lambda: [Session("08:00", "11:00")])
    trade_days: list[str] = field(default_factory=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri"])
 
 
@dataclass
class IndicatorsConfig:
    ema_fast: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    atr_period: int = 14
    atr_sl_multiplier: float = 2.0
    atr_tp_multiplier: float = 4.0
 
 
@dataclass
class ConfluenceConfig:
    min_score: float = 45.0
    decision_engine_weight: float = 0.4


@dataclass
class CandlePolicyConfig:
    enabled: bool = True
    min_strength: float = 50.0
    conflict_penalty: float = 15.0
    aligned_boost: float = 8.0
    veto_strength: float = 80.0


@dataclass
class NewsConfig:
    enabled: bool = False
    use_filter: bool = True
    use_confidence_adjustment: bool = True
    refresh_minutes: int = 30
    historical_lookback_days: int = 365
    calendar_scan_days: int = 2
    reaction_windows_minutes: list[int] = field(default_factory=lambda: [15, 60, 240])
    min_pattern_events: int = 30
    block_high_before_minutes: int = 20
    block_high_after_minutes: int = 45
    block_medium_enabled: bool = False
    block_medium_before_minutes: int = 10
    block_medium_after_minutes: int = 20
    confidence_boost_aligned: float = 6.0
    confidence_penalty_conflict: float = 10.0
    rss_urls: list[str] = field(default_factory=lambda: [
        "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
        "https://www.fxstreet.com/rss/news",
    ])
    manual_events: list[dict] = field(default_factory=list)
 
 
@dataclass
class HistoricalConfig:
    min_patterns: int = 15
    rsi_tolerance: float = 10.0
    min_future_move_atr_ratio: float = 0.3
 
 
@dataclass
class AIConfig:
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 180
    port: int | None = None
 
 
@dataclass
class LoopConfig:
    poll_seconds: int = 20
    reconnect_seconds: int = 15


@dataclass
class ObservabilityConfig:
    log_level: str = "INFO"  # QUIET | INFO | DEBUG
    heartbeat_seconds: int = 30
    show_symbol_summary: bool = True
 
 
@dataclass
class PIAConfig:
    # `mode` se conserva para compatibilidad con configuraciones v1.
    mode: str = "demo"
    execution: str = "simulated"
    account_type_required: str = "demo"
    symbols: list[str] = field(default_factory=lambda: ["EURUSD", "GBPUSD", "XAUUSD"])
    symbol_suffix: str = ""
    timeframe: str = "M15"
    entry_timeframe: str = "M5"
    candles: int = 300
    magic_number: int = 999999
    deviation: int = 50
    risk: RiskConfig = field(default_factory=RiskConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    indicators: IndicatorsConfig = field(default_factory=IndicatorsConfig)
    confluence: ConfluenceConfig = field(default_factory=ConfluenceConfig)
    candle_policy: CandlePolicyConfig = field(default_factory=CandlePolicyConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    historical: HistoricalConfig = field(default_factory=HistoricalConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
 
    @property
    def is_real(self) -> bool:
        """True si PIA debe enviar órdenes reales al broker."""
        return self.execution == "broker" or self.mode == "real"
 
    def broker_symbols(self) -> list[str]:
        """Símbolos tal como los espera el broker (con sufijo aplicado)."""
        return [f"{s}{self.symbol_suffix}" for s in self.symbols]
