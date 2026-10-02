"""Motor de decisión por símbolo (un ciclo completo).
 
Orquesta el pipeline para un símbolo: datos -> indicadores -> interpretación
-> memoria -> IA -> setup -> riesgo (sizing) -> RiskGuard (gobernanza) ->
ejecución (simulada o real) -> registro con explicación.
"""
 
from __future__ import annotations
 
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
 
from pia2.ai.analyst import Analysis, MarketSnapshot, TradingAnalyst
from pia2.brokers.base import BrokerInterface
from config.schema import PIAConfig
from pia2.memory.store import TradeRecord, TradeStore
from pia2.notify.base import Notifier
from pia2.observability.store import ObservabilityStore
from pia2.risk.risk_guard import RiskGuard
from pia2.risk.risk_manager import RiskManager
from pia2.scheduling.clock import within_session
from pia2.strategy.candles import analyze_candles
from pia2.strategy.indicators import add_indicators
from pia2.strategy.interpreter import (
    build_reference_setup,
    interpret_market,
    reference_trade_signal,
)
from pia2.strategy.trade_setup import build_trade_setup
from pia2.news.service import NewsService

try:
    from pia2.agents.historical_agent.historical_intelligence import HistoricalIntelligence
    HISTORICAL_AVAILABLE = True
except ImportError:
    HISTORICAL_AVAILABLE = False
 
 
@dataclass
class CycleResult:
    symbol: str
    executed: bool = False
    signal: str = "WAIT"
    reason: str = ""
    setup: dict = field(default_factory=dict)
 
 
class TradingEngine:
    def __init__(
        self,
        config: PIAConfig,
        broker: BrokerInterface,
        analyst: TradingAnalyst,
        store: TradeStore,
        guard: RiskGuard,
        notifier: Notifier,
    ):
        self.config = config
        self.broker = broker
        self.analyst = analyst
        self.store = store
        self.guard = guard
        self.notifier = notifier
        self.observability = ObservabilityStore("data/runtime/observability.db")
        self.risk_manager = RiskManager(
            config.risk.risk_per_trade_pct,
            max_margin_per_trade_usd=config.risk.max_margin_per_trade_usd,
        )
        
        # Inicializar HistoricalIntelligence si está disponible
        if HISTORICAL_AVAILABLE:
            self.historical = HistoricalIntelligence()
        else:
            self.historical = None

        self.news_service = NewsService(config.news, config.broker_symbols())

    def _should_log(self, level: str) -> bool:
        cfg_level = self.config.observability.log_level.upper()
        rank = {"QUIET": 0, "INFO": 1, "DEBUG": 2}
        return rank.get(cfg_level, 1) >= rank.get(level.upper(), 1)

    def _log(self, level: str, message: str) -> None:
        if self._should_log(level):
            self.notifier.send(f"[ENGINE:{level.upper()}] {message}")

    def _skip(self, result: CycleResult, reason: str, level: str = "INFO") -> CycleResult:
        result.reason = reason
        self._log(level, f"{result.symbol} skip | reason={reason}")
        return result

    def close(self) -> None:
        if self.news_service:
            self.news_service.store.close()

    def _apply_candle_policy(self, analysis: Analysis, candle_context: dict) -> Analysis:
        """Ajusta señal/confianza con patrón de velas según configuración."""
        policy = self.config.candle_policy
        if not policy.enabled:
            return analysis

        bias = str(candle_context.get("bias", "NEUTRAL")).upper()
        strength = float(candle_context.get("strength", 0) or 0)
        pattern = candle_context.get("pattern", "NONE")

        if bias not in {"BUY", "SELL"} or strength < policy.min_strength:
            return analysis

        original_signal = analysis.signal
        if original_signal not in {"BUY", "SELL"}:
            return analysis

        if original_signal == bias:
            analysis.confidence = min(100.0, analysis.confidence + policy.aligned_boost)
            analysis.reason = (
                f"{analysis.reason} | Velas confirman {bias} ({pattern}, fuerza {int(strength)})"
            ).strip(" |")
            return analysis

        if strength >= policy.veto_strength:
            analysis.signal = "WAIT"
            analysis.confidence = 0.0
            analysis.reason = (
                f"{analysis.reason} | Veto por velas opuestas {bias} ({pattern}, fuerza {int(strength)})"
            ).strip(" |")
            return analysis

        analysis.confidence = max(0.0, analysis.confidence - policy.conflict_penalty)
        analysis.reason = (
            f"{analysis.reason} | Velas contradicen ({pattern}, -{policy.conflict_penalty} confianza)"
        ).strip(" |")
        return analysis
 
    def run_symbol(self, symbol: str, now_utc: datetime | None = None) -> CycleResult:
        now = now_utc or datetime.now(timezone.utc)
        result = CycleResult(symbol=symbol)
 
        spec = self.broker.symbol_spec(symbol)
        if spec is None:
            return self._skip(result, "Sin especificaciones del símbolo")
 
        df = self.broker.get_candles(symbol, self.config.timeframe, self.config.candles)
        if df is None or len(df) < self.config.indicators.ema_slow:
            return self._skip(result, "Datos insuficientes")
 
        df = add_indicators(df, self.config.indicators)
        last = df.iloc[-1]
        price = float(last["close"])
        atr = float(last["ATR"])
        rsi = float(last["RSI"])
        candle_context = analyze_candles(df)
        self._log(
            "DEBUG",
            (
                f"{symbol} candles | pattern={candle_context.get('pattern')} "
                f"bias={candle_context.get('bias')} strength={candle_context.get('strength')}"
            ),
        )
 
        interp = interpret_market(price, float(last["EMA_FAST"]), float(last["EMA_SLOW"]), rsi, atr)
        reference_signal = reference_trade_signal(
            price=price,
            ema_fast=float(last["EMA_FAST"]),
            ema_slow=float(last["EMA_SLOW"]),
            rsi=rsi,
            atr=atr,
            candle_context=candle_context,
        )
        reference_setup = build_reference_setup(price, atr, reference_signal, self.config.indicators)
        if reference_signal != "WAIT":
            self._log(
                "DEBUG",
                f"{symbol} reference | signal={reference_signal} sl={reference_setup.stop_loss} tp={reference_setup.take_profit}",
            )

        # ---- noticias (actuales + históricas) ----
        news_decision = None
        if self.news_service and self.config.news.enabled:
            inserted = self.news_service.refresh_if_due(now)
            if inserted:
                self._log("INFO", f"news_refresh | inserted={inserted}")
            news_decision = self.news_service.build_decision(symbol, now)
            self._log(
                "DEBUG",
                (
                    f"{symbol} news | bias={news_decision.historical_bias} "
                    f"conf={news_decision.historical_confidence} block={news_decision.should_block}"
                ),
            )
            if news_decision.should_block:
                self.observability.record_signal(
                    symbol=symbol,
                    timestamp=now,
                    features={
                        "trend": interp["trend"],
                        "momentum": interp["momentum"],
                        "volatility": interp["volatility"],
                        "rsi": rsi,
                        "atr": atr,
                        "news": news_decision.context_text,
                    },
                    raw_llm_response="",
                    decision="WAIT",
                    block_filter="news",
                    latency_ms=0,
                )
                return self._skip(result, news_decision.block_reason)
 
        memory_context = self.store.stats(symbol)
        
        # Enriquecer memory_context con información histórica si está disponible
        if self.historical:
            try:
                historical_data = self.historical.analyze({
                    "symbol": symbol,
                    "trend": interp["trend"],
                    "rsi": rsi,
                })
                if historical_data and historical_data.get("patterns", 0) > 0:
                    patterns_count = historical_data.get("patterns", 0)
                    buy_prob = historical_data.get("buy_probability", 0)
                    sell_prob = historical_data.get("sell_probability", 0)
                    patterns_text = f"- Patrones similares encontrados: {patterns_count} casos\n"
                    patterns_text += f"  Probabilidad históricas: BUY={buy_prob}%, SELL={sell_prob}%"
                    memory_context["historical_patterns"] = patterns_text
                else:
                    memory_context["historical_patterns"] = ""
            except Exception as e:
                # Si hay error en historical, continuar sin ella
                self.notifier.send(f"[Advertencia] Error en HistoricalIntelligence: {e}")
                memory_context["historical_patterns"] = ""
        else:
            memory_context["historical_patterns"] = ""
 
        snapshot = MarketSnapshot(
            symbol=symbol,
            price=price,
            trend=interp["trend"],
            momentum=interp["momentum"],
            volatility=interp["volatility"],
            rsi=rsi,
            atr=atr,
            extra={
                "candles": candle_context,
                "news": {
                    "bias": news_decision.historical_bias if news_decision else "NEUTRAL",
                    "confidence": news_decision.historical_confidence if news_decision else 0.0,
                    "summary": news_decision.context_text if news_decision else "",
                },
            },
        )
        start = datetime.now(timezone.utc)
        analysis: Analysis = self.analyst.analyze(snapshot, memory_context)
        latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        self._log("DEBUG", f"{symbol} ai_raw | signal={analysis.signal} conf={analysis.confidence}")

        if analysis.signal in {"BUY", "SELL"} and reference_signal in {"BUY", "SELL"} and analysis.signal != reference_signal:
            analysis.confidence = max(0.0, analysis.confidence - 15.0)
            analysis.reason = (
                f"{analysis.reason} | Regla determinista en contra ({reference_signal}, -15 conf)"
            ).strip(" |")

        analysis = self._apply_candle_policy(analysis, candle_context)
        if self.news_service and news_decision:
            analysis = self.news_service.apply_confidence_policy(analysis, news_decision)
        self._log("DEBUG", f"{symbol} ai_final | signal={analysis.signal} conf={analysis.confidence}")
        result.signal = analysis.signal
 
        self.observability.record_signal(
            symbol=symbol,
            timestamp=now,
            features={
                "trend": interp["trend"],
                "momentum": interp["momentum"],
                "volatility": interp["volatility"],
                "rsi": rsi,
                "atr": atr,
                "candle_pattern": candle_context.get("pattern", "NONE"),
                "candle_bias": candle_context.get("bias", "NEUTRAL"),
                "candle_strength": candle_context.get("strength", 0),
                "news_bias": news_decision.historical_bias if news_decision else "NEUTRAL",
                "news_confidence": news_decision.historical_confidence if news_decision else 0.0,
            },
            raw_llm_response=analysis.raw,
            decision=analysis.signal,
            block_filter=None,
            latency_ms=latency_ms,
        )

        if analysis.signal == "WAIT":
            reason = analysis.reason or "IA sin señal"
            self._log("INFO", f"{symbol} | wait_reason={reason}")
            return self._skip(result, reason)
 
        if analysis.confidence < self.config.risk.min_confidence:
            return self._skip(
                result,
                f"Confianza {analysis.confidence} < mínimo {self.config.risk.min_confidence}",
            )
 
        setup = build_trade_setup(spec, analysis.signal, price, atr, self.config.indicators)
        if not setup.valid:
            return self._skip(result, f"Setup inválido: {setup.reason}")

        if self.config.risk.block_symbol_stacking and (
            self.broker.open_positions(symbol)
            or (not self.config.is_real and self.store.pending(symbol))
        ):
            return self._skip(result, "Ya existe una posición abierta en este símbolo")

        cooldown_minutes = self.config.risk.cooldown_minutes_after_loss
        if cooldown_minutes > 0:
            last_closed = self.store.latest_closed(symbol, analysis.signal)
            if last_closed and last_closed.status == "LOSS" and last_closed.closed_at:
                try:
                    closed_at = datetime.fromisoformat(last_closed.closed_at)
                    if closed_at.tzinfo is None:
                        closed_at = closed_at.replace(tzinfo=timezone.utc)
                    if (now - closed_at) < timedelta(minutes=cooldown_minutes):
                        return self._skip(
                            result,
                            (
                                f"Cooldown post-loss activo ({cooldown_minutes}m) "
                                f"para {symbol} {analysis.signal}"
                            ),
                        )
                except ValueError:
                    pass
 
        # ---- gobernanza de riesgo (RiskGuard) ----
        account = self.broker.account()
        if account is None:
            return self._skip(result, "Sin información de cuenta")
 
        tick = self.broker.get_tick(symbol)
        spread_points = (tick.spread_points / spec.point) if (tick and spec.point) else 0.0
        current_positions = self.broker.open_positions()
        if not self.config.is_real:
            current_positions = current_positions + [
                position for position in self.store.pending() if position.ticket is None
            ]
        open_positions = len(current_positions)
        if not self.guard.currency_exposure_allowed(symbol, setup.signal, current_positions):
            return self._skip(result, "Exposición por divisa ya comprometida")
        session_ok = within_session(now, self.config.schedule)
 
        self.observability.record_account_snapshot(
            timestamp=now,
            symbol=symbol,
            balance=account.balance,
            equity=account.equity,
            margin_free=account.margin_free,
            margin_level=account.margin_level,
            open_positions=open_positions,
        )

        guard_decision = self.guard.can_open_trade(
            today=now.date(),
            balance=account.balance,
            equity=account.equity,
            open_positions=open_positions,
            spread_points=spread_points,
            within_session=session_ok,
            symbol=symbol,
        )
        if not guard_decision.allowed:
            return self._skip(result, f"RiskGuard: {guard_decision.reason}")
 
        # ---- tamaño de posición ----
        margin_estimator = None
        if hasattr(self.broker, "estimate_margin"):
            margin_estimator = lambda volume: self.broker.estimate_margin(
                symbol, setup.signal, volume, setup.entry
            )

        sizing = self.risk_manager.size(
            spec,
            account.balance,
            setup.sl_distance,
            account_leverage=account.leverage,
            margin_estimator=margin_estimator,
            margin_free=account.margin_free,
            margin_level=account.margin_level,
        )
        if not sizing.approved:
            return self._skip(result, f"Sizing: {sizing.reason}")
 
        result.setup = {
            "signal": setup.signal,
            "entry": setup.entry,
            "stop_loss": setup.stop_loss,
            "take_profit": setup.take_profit,
            "risk_reward": setup.risk_reward,
            "volume": sizing.volume,
            "confidence": analysis.confidence,
        }
 
        # ---- ejecución (demo simula, real envía orden) ----
        ticket = None
        if self.config.is_real:
            order = self.broker.place_order(
                symbol=symbol,
                direction=setup.signal,
                volume=sizing.volume,
                stop_loss=setup.stop_loss,
                take_profit=setup.take_profit,
                magic=self.config.magic_number,
                comment=f"PIA_{setup.signal}",
            )
            if not order.ok:
                self.observability.record_order(
                    symbol=symbol,
                    timestamp=now,
                    direction=setup.signal,
                    volume=sizing.volume,
                    price=entry_price if 'entry_price' in locals() else setup.entry,
                    spread_points=spread_points,
                    status="REJECTED",
                    comment=order.reason,
                )
                return self._skip(result, f"Orden rechazada: {order.reason}")
            ticket = order.ticket
            entry_price = order.price or setup.entry
        else:
            entry_price = setup.entry

        self.observability.record_order(
            symbol=symbol,
            timestamp=now,
            direction=setup.signal,
            volume=sizing.volume,
            price=entry_price,
            spread_points=spread_points,
            status="OPENED",
            comment=f"{setup.signal}:{symbol}",
        )
 
        record = TradeRecord(
            symbol=symbol,
            direction=setup.signal,
            confidence=analysis.confidence,
            entry_price=entry_price,
            stop_loss=setup.stop_loss,
            take_profit=setup.take_profit,
            volume=sizing.volume,
            reason=analysis.reason,
            context={
                "mode": self.config.mode,
                "rsi": rsi,
                "atr": atr,
                "trend": interp["trend"],
                "momentum": interp["momentum"],
                "volatility": interp["volatility"],
                "candle_pattern": candle_context.get("pattern", "NONE"),
                "candle_bias": candle_context.get("bias", "NEUTRAL"),
                "candle_strength": candle_context.get("strength", 0),
                "news_bias": news_decision.historical_bias if news_decision else "NEUTRAL",
                "news_confidence": news_decision.historical_confidence if news_decision else 0.0,
                "news_summary": news_decision.context_text if news_decision else "",
                "risk_reward": setup.risk_reward,
                "bar_time": str(last["time"]) if "time" in df.columns else None,
            },
            ticket=ticket,
        )
        self.store.save_decision(record)
        self.guard.register_trade_opened()
 
        result.executed = True
        result.reason = "Operación abierta" if self.config.is_real else "Operación simulada (demo)"
        self._log("INFO", f"{symbol} open | signal={result.signal} | reason={result.reason}")
 
        self.notifier.send(self._explain(symbol, setup, sizing.volume, analysis))
        return result
 
    def _explain(self, symbol, setup, volume, analysis: Analysis) -> str:
        modo = "REAL" if self.config.is_real else "DEMO (simulado)"
        return (
            f"[{modo}] {setup.signal} {symbol}\n"
            f"Entrada: {setup.entry} | SL: {setup.stop_loss} | TP: {setup.take_profit} "
            f"(R:R {setup.risk_reward})\n"
            f"Volumen: {volume} | Confianza IA: {analysis.confidence}\n"
            f"Razón: {analysis.reason}"
        )
