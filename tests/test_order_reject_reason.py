from dataclasses import replace
from datetime import date, datetime, timezone

from pia2.ai.analyst import TradingAnalyst
from pia2.brokers.base import OrderResult
from pia2.brokers.paper_broker import PaperBroker
from pia2.core.engine import TradingEngine
from pia2.memory.store import TradeStore
from pia2.risk.risk_guard import RiskGuard
from tests.test_analyst import FakeClient


class RejectingBroker(PaperBroker):
    def place_order(
        self,
        symbol,
        direction,
        volume,
        stop_loss,
        take_profit,
        magic,
        comment="",
    ):
        return OrderResult(
            ok=False,
            reason="Orden rechazada [TRADE_RETCODE_MARKET_CLOSED]: ",
        )


class SilentNotifier:
    def send(self, message):
        pass


class NoopObservability:
    def record_signal(self, **kwargs):
        pass

    def record_account_snapshot(self, **kwargs):
        pass

    def record_order(self, **kwargs):
        pass


def test_engine_does_not_duplicate_order_rejected_prefix(
    tmp_path, always_on_config, eurusd_spec, uptrend_candles
):
    config = replace(always_on_config, execution="broker")
    broker = RejectingBroker(balance=10000)
    broker.connect()
    broker.set_spec(eurusd_spec)
    broker.set_candles("EURUSD", uptrend_candles)
    last_close = float(uptrend_candles.iloc[-1]["close"])
    broker.set_tick("EURUSD", bid=last_close, ask=last_close + 0.00002)

    store = TradeStore(str(tmp_path / "order-reject.db"))
    guard = RiskGuard(config.risk)
    guard.start_day(date(2026, 7, 17), 10000)
    engine = TradingEngine(
        config,
        broker,
        TradingAnalyst(FakeClient('{"signal":"BUY","confidence":80,"reason":"test"}')),
        store,
        guard,
        SilentNotifier(),
    )
    engine.observability = NoopObservability()

    result = engine.run_symbol(
        "EURUSD",
        datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc),
    )

    assert result.executed is False
    assert result.reason.count("Orden rechazada") == 1
    assert result.reason == "Orden rechazada [TRADE_RETCODE_MARKET_CLOSED]: "
    store.close()
