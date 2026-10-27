from datetime import datetime, timezone

from config.schema import PIAConfig
from pia2.brokers.base import ClosedDeal
from pia2.core.reconciler import backfill_history, reconcile
from pia2.memory.store import TradeRecord, TradeStore
from pia2.risk.risk_guard import RiskGuard

MAGIC = 999


def _deal(ticket, profit, magic=MAGIC, commission=0.0, swap=0.0, fee=0.0, day=10, **kw):
    return ClosedDeal(
        ticket=ticket, symbol="EURUSD", direction="BUY", volume=0.1,
        entry_price=1.1, exit_price=1.101, profit=profit,
        close_time=datetime(2026, 10, day, 12, 0, tzinfo=timezone.utc),
        magic=magic, commission=commission, swap=swap, fee=fee, **kw,
    )


class FakeBroker:
    def __init__(self, deals, open_tickets=()):
        self.deals = deals
        self.open_tickets = open_tickets

    def closed_deals_since(self, since, magic=None):
        return [
            d for d in self.deals
            if d.close_time >= since and (magic is None or d.magic == magic)
        ]

    def open_positions(self):
        return [type("P", (), {"ticket": t})() for t in self.open_tickets]


def _setup(tmp_path):
    store = TradeStore(str(tmp_path / "trades.db"))
    config = PIAConfig(mode="real", execution="broker", magic_number=MAGIC)
    guard = RiskGuard(config.risk, store=store, timezone_name="UTC")
    return store, config, guard


def test_deal_without_local_row_is_inserted(tmp_path):
    store, config, guard = _setup(tmp_path)
    broker = FakeBroker([_deal(1, -5.0, commission=-1.0, swap=-0.5, fee=-0.25)])

    assert backfill_history(config, broker, store, guard) == 1
    trade = store.closed()[0]
    assert (trade.status, trade.profit, trade.symbol) == ("LOSS", -6.75, "EURUSD")
    assert trade.direction == "BUY" and trade.volume == 0.1 and trade.ticket == 1
    assert trade.closed_at.startswith("2026-10-10T12:00:00")
    store.close()


def test_existing_row_is_updated_not_duplicated(tmp_path):
    store, config, guard = _setup(tmp_path)
    store.save_decision(TradeRecord(
        symbol="EURUSD", direction="BUY", confidence=80, entry_price=1.1,
        stop_loss=1.09, take_profit=1.11, volume=0.1, ticket=1,
    ))
    broker = FakeBroker([_deal(1, 10.0)])

    assert reconcile(config, broker, store, guard, datetime(2026, 10, 1, tzinfo=timezone.utc)) == 1
    assert len(store.closed()) == 1
    assert store.closed()[0].confidence == 80
    assert reconcile(config, broker, store, guard, datetime(2026, 10, 1, tzinfo=timezone.utc)) == 0
    assert store._conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
    store.close()


def test_other_magic_is_ignored(tmp_path):
    store, config, guard = _setup(tmp_path)
    broker = FakeBroker([_deal(1, 10.0, magic=123)])
    assert backfill_history(config, broker, store, guard) == 0

    # Aunque el broker no filtre por magic, no se inserta.
    broker.closed_deals_since = lambda since, magic=None: [_deal(2, 10.0, magic=123)]
    assert backfill_history(config, broker, store, guard) == 0
    assert store.closed() == []
    store.close()


def test_backfill_matches_deal_totals_and_is_idempotent(tmp_path):
    store, config, guard = _setup(tmp_path)
    deals = [
        _deal(1, 10.0, day=6), _deal(2, -4.0, commission=-1.0, day=7),
        _deal(3, 2.0, day=8), _deal(4, 5.0, commission=-5.0, day=9),
        _deal(5, 99.0, magic=1, day=9),
    ]
    broker = FakeBroker(deals)

    assert backfill_history(config, broker, store, guard) == 4
    assert backfill_history(config, broker, store, guard) == 0
    stats = store.stats()
    assert stats["total_trades"] == 4
    assert (stats["wins"], stats["losses"]) == (2, 1)
    assert stats["net_profit"] == 7.0
    assert stats["gross_profit"] == 12.0 and stats["gross_loss"] == 5.0
    assert stats["profit_factor"] == 2.4
    store.close()


def test_partial_closes_are_merged_and_open_positions_skipped(tmp_path):
    store, config, guard = _setup(tmp_path)
    broker = FakeBroker(
        [_deal(1, 3.0, day=8), _deal(1, 4.0, day=9), _deal(2, 1.0)], open_tickets=(2,)
    )

    assert backfill_history(config, broker, store, guard) == 1
    assert [(t.ticket, t.profit, t.volume) for t in store.closed()] == [(1, 7.0, 0.2)]
    store.close()


def _row(ticket, status, profit):
    return TradeRecord(
        symbol="EURUSD", direction="BUY", confidence=70, entry_price=1.1,
        stop_loss=1.09, take_profit=1.11, volume=0.1, ticket=ticket,
        status=status, profit=profit,
    )


def test_unknown_row_is_resolved_with_real_deal(tmp_path):
    store, config, guard = _setup(tmp_path)
    store.save_decision(_row(1, "UNKNOWN", 0.0))
    broker = FakeBroker([_deal(1, 8.0, commission=-1.0)])

    assert backfill_history(config, broker, store, guard) == 1
    assert store._conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
    trade = store.closed()[0]
    assert (trade.status, trade.profit) == ("WIN", 7.0)
    store.close()


def test_backfill_corrects_closed_rows_but_normal_reconcile_does_not(tmp_path):
    store, config, guard = _setup(tmp_path)
    store.save_decision(_row(1, "BREAKEVEN", 0.0))
    broker = FakeBroker([_deal(1, 0.0, commission=-0.6)])
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)

    assert reconcile(config, broker, store, guard, since) == 0
    assert store.closed()[0].status == "BREAKEVEN"

    assert backfill_history(config, broker, store, guard) == 1
    assert (store.closed()[0].status, store.closed()[0].profit) == ("LOSS", -0.6)
    assert backfill_history(config, broker, store, guard) == 0
    store.close()
