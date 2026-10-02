from datetime import datetime, timezone

from config.schema import PIAConfig
from pia2.brokers.base import ClosedDeal
from pia2.core.reconciler import reconcile
from pia2.memory.store import TradeRecord, TradeStore
from pia2.risk.risk_guard import RiskGuard


class DealBroker:
    def closed_deals_since(self, since, magic=None):
        self.range = (since, magic)
        return [
            ClosedDeal(
                ticket=42,
                symbol="EURUSD",
                direction="BUY",
                volume=0.1,
                entry_price=1.1,
                exit_price=1.101,
                profit=10.0,
                close_time=datetime(2026, 7, 17, 15, 0, tzinfo=timezone.utc),
                commission=-1.0,
                swap=-0.5,
                fee=-0.25,
            )
        ]

    def open_positions(self):
        return []


def test_real_reconciliation_uses_deal_time_and_net_costs(tmp_path):
    store = TradeStore(str(tmp_path / "trades.db"))
    store.save_decision(
        TradeRecord(
            symbol="EURUSD", direction="BUY", confidence=80,
            entry_price=1.1, stop_loss=1.09, take_profit=1.11,
            volume=0.1, ticket=42,
        )
    )
    config = PIAConfig(mode="real", execution="broker", magic_number=999)
    guard = RiskGuard(config.risk, store=store, timezone_name="UTC")
    guard.start_day(datetime(2026, 7, 17, tzinfo=timezone.utc).date(), 1000)
    broker = DealBroker()

    assert reconcile(config, broker, store, guard) == 1
    closed = store.closed("EURUSD")[0]
    assert closed.profit == 8.25
    assert closed.closed_at.startswith("2026-07-17T15:00:00")
    store.close()


def test_real_reconciliation_marks_missing_pending_as_unknown(tmp_path):
    store = TradeStore(str(tmp_path / "trades.db"))
    store.save_decision(
        TradeRecord(
            symbol="EURUSD", direction="BUY", confidence=80,
            entry_price=1.1, stop_loss=1.09, take_profit=1.11,
            volume=0.1, ticket=99,
        )
    )
    config = PIAConfig(mode="real", execution="broker")
    guard = RiskGuard(config.risk, store=store)

    assert reconcile(config, DealBroker(), store, guard) == 0
    assert store.pending() == []
    row = store._conn.execute("SELECT status FROM trades WHERE ticket = 99").fetchone()
    assert row["status"] == "UNKNOWN"
    store.close()