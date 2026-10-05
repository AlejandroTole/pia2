from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from config.schema import PIAConfig, RiskConfig
from pia2.brokers.base import Position, Tick
from pia2.brokers.paper_broker import PaperBroker
from pia2.core.engine import TradingEngine
from pia2.core.orchestrator import Orchestrator
from pia2.market.instruments import money_profit
from pia2.memory.store import TradeRecord, TradeStore


class FakeBroker:
    def __init__(self, positions, ticks, modify_result=True, close_result=True):
        self.positions = positions
        self.ticks = ticks
        self.modify_result = modify_result
        self.close_result = close_result
        self.modify_calls = []
        self.close_calls = []

    def open_positions(self):
        return list(self.positions)

    def get_tick(self, symbol):
        return self.ticks.get(symbol)

    def modify_position_sl(self, ticket, stop_loss):
        self.modify_calls.append((ticket, stop_loss))
        if self.modify_result:
            for position in self.positions:
                if position.ticket == ticket:
                    position.stop_loss = stop_loss
        return self.modify_result

    def close_position(self, ticket):
        self.close_calls.append(ticket)
        return self.close_result


class SilentNotifier:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


@pytest.fixture
def store(tmp_path):
    trade_store = TradeStore(str(tmp_path / "live-exits.db"))
    yield trade_store
    trade_store.close()


def _position(ticket=10, magic=1234, direction="BUY"):
    return Position(
        ticket=ticket,
        symbol="EURUSD",
        direction=direction,
        volume=0.1,
        entry_price=1.1000,
        stop_loss=1.0960,
        take_profit=1.1080,
        profit=0.0,
        magic=magic,
    )


def _engine(store, broker, *, is_real=True, be_trigger=0.5, max_holding=60):
    config = PIAConfig(
        execution="broker" if is_real else "simulated",
        magic_number=1234,
        risk=RiskConfig(
            breakeven_trigger_atr=be_trigger,
            max_holding_minutes=max_holding,
        ),
    )
    engine = TradingEngine.__new__(TradingEngine)
    engine.config = config
    engine.broker = broker
    engine.store = store
    engine.notifier = SilentNotifier()
    return engine


def _save_trade(store, ticket=10, opened_at=None, atr=0.002, direction="BUY"):
    store.save_decision(
        TradeRecord(
            symbol="EURUSD",
            direction=direction,
            confidence=80,
            entry_price=1.1000,
            stop_loss=1.0960,
            take_profit=1.1080,
            volume=0.1,
            context={"atr": atr},
            ticket=ticket,
            opened_at=opened_at or datetime.now(timezone.utc).isoformat(),
        )
    )


def test_breakeven_arms_only_once(store):
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    broker = FakeBroker(
        [_position()],
        {"EURUSD": Tick("EURUSD", bid=1.1011, ask=1.1012, time=now)},
    )
    _save_trade(store, opened_at=(now - timedelta(minutes=5)).isoformat())
    engine = _engine(store, broker)

    first = engine.manage_positions(now)
    second = engine.manage_positions(now + timedelta(seconds=20))

    assert first == {"checked": 1, "be_armed": 1, "closed": 0}
    assert second == {"checked": 1, "be_armed": 0, "closed": 0}
    assert broker.modify_calls == [(10, 1.1000)]
    assert store.is_be_armed(10)


def test_breakeven_flag_survives_store_reopen(tmp_path):
    db_path = str(tmp_path / "persistent-flags.db")
    store = TradeStore(db_path)
    assert not store.is_be_armed(10)
    store.mark_be_armed(10)
    store.close()

    reopened = TradeStore(db_path)
    try:
        assert reopened.is_be_armed(10)
    finally:
        reopened.close()


def test_sell_breakeven_uses_ask_price(store):
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    position = _position(direction="SELL")
    broker = FakeBroker(
        [position],
        {"EURUSD": Tick("EURUSD", bid=1.0988, ask=1.0989, time=now)},
    )
    _save_trade(
        store,
        opened_at=(now - timedelta(minutes=5)).isoformat(),
        direction="SELL",
    )

    result = _engine(store, broker).manage_positions(now)

    assert result["be_armed"] == 1
    assert broker.modify_calls == [(10, 1.1000)]


def test_timeout_closes_position_opened_two_hours_ago(store):
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    broker = FakeBroker(
        [_position()],
        {"EURUSD": Tick("EURUSD", bid=1.1000, ask=1.1001, time=now)},
    )
    _save_trade(store, opened_at=(now - timedelta(hours=2)).isoformat())

    result = _engine(store, broker, be_trigger=0).manage_positions(now)

    assert result == {"checked": 1, "be_armed": 0, "closed": 1}
    assert broker.close_calls == [10]


def test_ignores_other_magic_and_unregistered_tickets(store):
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    broker = FakeBroker(
        [_position(ticket=10, magic=999), _position(ticket=11, magic=1234)],
        {"EURUSD": Tick("EURUSD", bid=1.1011, ask=1.1012, time=now)},
    )
    _save_trade(store, ticket=10, opened_at=(now - timedelta(minutes=5)).isoformat())

    result = _engine(store, broker).manage_positions(now)

    assert result == {"checked": 0, "be_armed": 0, "closed": 0}
    assert broker.modify_calls == []
    assert broker.close_calls == []


def test_failed_sl_update_is_not_marked_armed(store):
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    broker = FakeBroker(
        [_position()],
        {"EURUSD": Tick("EURUSD", bid=1.1011, ask=1.1012, time=now)},
        modify_result=False,
    )
    _save_trade(store, opened_at=(now - timedelta(minutes=5)).isoformat())

    result = _engine(store, broker).manage_positions(now)

    assert result == {"checked": 1, "be_armed": 0, "closed": 0}
    assert broker.modify_calls == [(10, 1.1000)]
    assert not store.is_be_armed(10)


def test_position_exception_does_not_skip_later_positions(store):
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    broker = FakeBroker(
        [_position(ticket=10), _position(ticket=11)],
        {},
    )
    _save_trade(store, ticket=10, opened_at=(now - timedelta(minutes=5)).isoformat())
    _save_trade(store, ticket=11, opened_at=(now - timedelta(minutes=5)).isoformat())
    first_tick = True

    def fail_once(symbol):
        nonlocal first_tick
        if first_tick:
            first_tick = False
            raise RuntimeError("tick temporalmente no disponible")
        return Tick(symbol, bid=1.1011, ask=1.1012, time=now)

    broker.get_tick = fail_once
    engine = _engine(store, broker)

    result = engine.manage_positions(now)

    assert result == {"checked": 2, "be_armed": 1, "closed": 0}
    assert broker.modify_calls == [(11, 1.1000)]
    assert not store.is_be_armed(10)
    assert store.is_be_armed(11)


def test_simulated_mode_with_no_ticket_is_noop(store):
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    broker = FakeBroker([], {})
    _save_trade(store, ticket=None, opened_at=(now - timedelta(hours=2)).isoformat())

    result = _engine(store, broker, is_real=False).manage_positions(now)

    assert result == {"checked": 0, "be_armed": 0, "closed": 0}
    assert broker.modify_calls == []
    assert broker.close_calls == []


def test_paper_broker_modify_and_close_position(eurusd_spec):
    broker = PaperBroker()
    broker.set_spec(eurusd_spec)
    broker.set_tick("EURUSD", bid=1.1010, ask=1.1012)
    order = broker.place_order(
        "EURUSD", "BUY", 0.1, 1.0960, 1.1080, magic=1234
    )
    assert order.ok and order.ticket is not None

    assert broker.modify_position_sl(order.ticket, 1.1000)
    assert broker.open_positions()[0].stop_loss == 1.1000
    assert broker.close_position(order.ticket)
    assert broker.open_positions() == []
    closed = broker.closed_deals_since(datetime.min.replace(tzinfo=timezone.utc))
    assert len(closed) == 1
    assert closed[0].exit_price == 1.1010
    assert closed[0].profit == money_profit(
        eurusd_spec, "BUY", order.price, 1.1010, 0.1
    )
    assert not broker.close_position(order.ticket)


def test_orchestrator_manages_positions_before_kill_switch(monkeypatch):
    events = []
    config = PIAConfig(execution="broker")
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.config = config
    orchestrator.broker = SimpleNamespace(is_connected=lambda: True)
    orchestrator.engine = SimpleNamespace(
        manage_positions=lambda *args: (
            events.append("manage")
            or {"checked": len(args), "be_armed": 0, "closed": 0}
        )
    )
    orchestrator.store = object()
    orchestrator.guard = object()
    orchestrator.notifier = SilentNotifier()
    orchestrator._tick_seq = 0
    orchestrator._last_reconcile = None
    orchestrator._last_heartbeat = None
    orchestrator._kill_switch_active = lambda: events.append("kill") or True
    monkeypatch.setattr(
        "pia2.core.orchestrator.reconcile",
        lambda *args: events.append("reconcile") or len(args) - 5,
    )

    orchestrator._tick()

    assert events == ["reconcile", "manage", "kill"]


def test_orchestrator_catches_manager_exception(monkeypatch):
    events = []
    config = PIAConfig(execution="broker")
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.config = config
    orchestrator.broker = SimpleNamespace(is_connected=lambda: True)

    def fail_manager(*args):
        events.append("manage")
        assert len(args) == 1
        raise RuntimeError("manager failure")

    orchestrator.engine = SimpleNamespace(manage_positions=fail_manager)
    orchestrator.store = object()
    orchestrator.guard = object()
    orchestrator.notifier = SilentNotifier()
    orchestrator._tick_seq = 0
    orchestrator._last_reconcile = None
    orchestrator._last_heartbeat = None
    orchestrator._kill_switch_active = lambda: events.append("kill") or True
    monkeypatch.setattr(
        "pia2.core.orchestrator.reconcile",
        lambda *args: events.append("reconcile") or len(args) - 5,
    )

    orchestrator._tick()

    assert events == ["reconcile", "manage", "kill"]
