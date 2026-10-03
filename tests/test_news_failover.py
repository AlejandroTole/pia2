"""Tests de la política de fallo del módulo de noticias (core/engine.py).

Si la fuente de noticias falla (red, RSS, parseo):
- fail_open=True  -> el ciclo sigue sin noticias (neutral) y el fallo queda
  visible (log WARNING + observabilidad con block_filter="news_error").
- fail_open=False -> el símbolo se omite en ese ciclo (fail-closed).
"""

from datetime import date, datetime, timezone

from pia2.ai.analyst import TradingAnalyst
from pia2.brokers.paper_broker import PaperBroker
from pia2.core.engine import TradingEngine
from pia2.memory.store import TradeStore
from pia2.notify.base import Notifier
from pia2.risk.risk_guard import RiskGuard


class FakeClient:
    def __init__(self, response: str):
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


class ExplodingNewsService:
    """Simula una fuente de noticias caída."""

    def refresh_if_due(self, now):
        raise ConnectionError("RSS caído")

    def build_decision(self, symbol, now):  # pragma: no cover
        raise AssertionError("no debería llamarse si refresh_if_due falla")


class SilentNotifier(Notifier):
    def send(self, message: str) -> None:
        pass


def _build_engine(tmp_path, config, eurusd_spec, uptrend_candles, *, fail_open: bool):
    broker = PaperBroker(balance=10000)
    broker.connect()
    broker.set_spec(eurusd_spec)
    broker.set_candles("EURUSD", uptrend_candles)
    last_close = float(uptrend_candles.iloc[-1]["close"])
    broker.set_tick("EURUSD", bid=last_close, ask=last_close + 0.00002)

    store = TradeStore(str(tmp_path / "pia.db"))
    guard = RiskGuard(config.risk)
    guard.start_day(date(2026, 7, 17), 10000)

    analyst = TradingAnalyst(FakeClient('{"signal":"WAIT","confidence":0,"reason":"calma"}'))
    engine = TradingEngine(config, broker, analyst, store, guard, SilentNotifier())

    config.news.enabled = True
    config.news.fail_open = fail_open
    engine.news_service = ExplodingNewsService()
    return engine, store


def test_news_failure_fail_open_continues(tmp_path, always_on_config, eurusd_spec, uptrend_candles):
    engine, store = _build_engine(
        tmp_path, always_on_config, eurusd_spec, uptrend_candles, fail_open=True
    )
    try:
        result = engine.run_symbol("EURUSD", datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc))
    finally:
        store.close()
    # El ciclo sobrevivió al fallo de noticias: no se omitió por noticias.
    assert result.signal == "WAIT"
    assert "Noticias no disponibles" not in result.reason


def test_news_failure_fail_closed_skips_symbol(tmp_path, always_on_config, eurusd_spec, uptrend_candles):
    engine, store = _build_engine(
        tmp_path, always_on_config, eurusd_spec, uptrend_candles, fail_open=False
    )
    try:
        result = engine.run_symbol("EURUSD", datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc))
    finally:
        store.close()
    assert result.executed is False
    assert "Noticias no disponibles" in result.reason
