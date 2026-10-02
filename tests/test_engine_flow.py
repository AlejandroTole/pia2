from datetime import date, datetime, timezone
 
import pandas as pd
 
from pia2.ai.analyst import TradingAnalyst
from pia2.brokers.paper_broker import PaperBroker
from pia2.core.engine import TradingEngine
from pia2.core.reconciler import reconcile
from pia2.memory.store import TradeRecord, TradeStore
from pia2.notify.base import Notifier
from pia2.risk.risk_guard import RiskGuard
from tests.test_analyst import FakeClient
 
 
class SilentNotifier(Notifier):
    def __init__(self):
        self.messages = []
 
    def send(self, message: str) -> None:
        self.messages.append(message)
 
 
def build_broker(eurusd_spec, uptrend_candles):
    broker = PaperBroker(balance=10000)
    broker.connect()
    broker.set_spec(eurusd_spec)
    broker.set_candles("EURUSD", uptrend_candles)
    last_close = float(uptrend_candles.iloc[-1]["close"])
    broker.set_tick("EURUSD", bid=last_close, ask=last_close + 0.00002)
    return broker
 
 
def test_engine_opens_simulated_trade(tmp_path, always_on_config, eurusd_spec, uptrend_candles):
    broker = build_broker(eurusd_spec, uptrend_candles)
    store = TradeStore(str(tmp_path / "pia.db"))
    guard = RiskGuard(always_on_config.risk)
    guard.start_day(date(2026, 7, 17), 10000)
    notifier = SilentNotifier()
 
    analyst = TradingAnalyst(FakeClient('{"signal":"BUY","confidence":80,"reason":"tendencia"}'))
    engine = TradingEngine(always_on_config, broker, analyst, store, guard, notifier)
 
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
    result = engine.run_symbol("EURUSD", now)
 
    assert result.executed is True
    assert result.signal == "BUY"
    pending = store.pending("EURUSD")
    assert len(pending) == 1
    trade = pending[0]
    assert trade.direction == "BUY"
    assert trade.take_profit > trade.entry_price   # BUY -> TP arriba
    assert trade.stop_loss < trade.entry_price      # BUY -> SL abajo
    assert trade.volume > 0
    assert guard.trades_today == 1
    store.close()
 
 
def test_engine_waits_on_low_confidence(tmp_path, always_on_config, eurusd_spec, uptrend_candles):
    broker = build_broker(eurusd_spec, uptrend_candles)
    store = TradeStore(str(tmp_path / "pia.db"))
    guard = RiskGuard(always_on_config.risk)
    guard.start_day(date(2026, 7, 17), 10000)
 
    analyst = TradingAnalyst(FakeClient('{"signal":"BUY","confidence":30,"reason":"débil"}'))
    engine = TradingEngine(always_on_config, broker, analyst, store, guard, SilentNotifier())
 
    result = engine.run_symbol("EURUSD", datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc))
    assert result.executed is False
    assert store.pending("EURUSD") == []
    store.close()
 
 
def test_reconcile_demo_closes_win(tmp_path, always_on_config, eurusd_spec, uptrend_candles):
    broker = build_broker(eurusd_spec, uptrend_candles)
    store = TradeStore(str(tmp_path / "pia.db"))
    guard = RiskGuard(always_on_config.risk)
    guard.start_day(date(2026, 7, 17), 10000)
 
    entry = 1.10000
    tp = 1.10400
    sl = 1.09800
    record = TradeRecord(
        symbol="EURUSD", direction="BUY", confidence=80, entry_price=entry,
        stop_loss=sl, take_profit=tp, volume=1.0, reason="test",
        context={"bar_time": "2026-07-01 00:00:00"},
    )
    store.save_decision(record)
 
    # Velas posteriores que tocan el TP (high >= tp).
    future = pd.DataFrame([
        {"time": pd.Timestamp("2026-07-02 00:00:00"), "open": entry, "high": 1.10500,
         "low": 1.09950, "close": 1.10450, "volume": 100},
    ])
    broker.set_candles("EURUSD", future)
 
    closed = reconcile(always_on_config, broker, store, guard)
    assert closed == 1
    done = store.closed("EURUSD")
    assert len(done) == 1
    assert done[0].status == "WIN"
    # +0.0040 con 1 lote, tick 0.00001, tick_value 1.0 -> 400 * 1.0 = 400
    assert round(done[0].profit, 2) == 400.0
    store.close()
 
 
def test_reconcile_demo_closes_loss(tmp_path, always_on_config, eurusd_spec):
    broker = PaperBroker(balance=10000)
    broker.connect()
    broker.set_spec(eurusd_spec)
    store = TradeStore(str(tmp_path / "pia.db"))
    guard = RiskGuard(always_on_config.risk)
    guard.start_day(date(2026, 7, 17), 10000)
 
    record = TradeRecord(
        symbol="EURUSD", direction="BUY", confidence=80, entry_price=1.10000,
        stop_loss=1.09800, take_profit=1.10400, volume=1.0, reason="test",
        context={"bar_time": "2026-07-01 00:00:00"},
    )
    store.save_decision(record)
 
    future = pd.DataFrame([
        {"time": pd.Timestamp("2026-07-02 00:00:00"), "open": 1.10000, "high": 1.10050,
         "low": 1.09700, "close": 1.09750, "volume": 100},
    ])
    broker.set_candles("EURUSD", future)
 
    reconcile(always_on_config, broker, store, guard)
    done = store.closed("EURUSD")
    assert done[0].status == "LOSS"
    assert round(done[0].profit, 2) == -200.0  # -0.0020 * 100000... -> 200 ticks * 1.0
    store.close()