from datetime import date, datetime, timezone
 
from config.schema import RiskConfig
from pia2.market.instruments import SymbolSpec
from pia2.risk.risk_guard import RiskGuard
from pia2.risk.risk_manager import RiskManager
from pia2.memory.store import TradeStore
from pia2.brokers.base import Position
 
 
def eurusd_spec():
    return SymbolSpec(
        name="EURUSD", digits=5, point=0.00001, tick_size=0.00001, tick_value=1.0,
        contract_size=100000, volume_step=0.01,
    )
 
 
def test_position_sizing_matches_risk():
    rm = RiskManager(risk_per_trade_pct=1.0, max_margin_per_trade_usd=5000)
    spec = eurusd_spec()
    # balance 10000, riesgo 1% = $100. SL distance 0.0010 (10 pips).
    # loss_per_lot = (0.0010/0.00001)*1.0 = 100 -> volume = 100/100 = 1.0
    sizing = rm.size(spec, balance=10000, sl_distance=0.0010, account_leverage=100)
    assert sizing.approved
    assert sizing.risk_amount == 100.0
    assert sizing.volume == 1.0
 
 
def test_position_sizing_rejects_bad_input():
    rm = RiskManager(1.0)
    spec = eurusd_spec()
    assert not rm.size(spec, balance=0, sl_distance=0.001).approved
    assert not rm.size(spec, balance=1000, sl_distance=0).approved


def test_position_sizing_blocks_when_estimated_margin_exceeds_limit():
    rm = RiskManager(risk_per_trade_pct=1.0, max_margin_per_trade_usd=500)
    spec = eurusd_spec()
    sizing = rm.size(spec, balance=10000, sl_distance=0.0010, account_leverage=100)
    assert not sizing.approved
    assert "Margen estimado" in sizing.reason


def test_position_sizing_rounds_down_and_reports_actual_risk():
    rm = RiskManager(risk_per_trade_pct=1.0, max_margin_per_trade_usd=5000)
    spec = eurusd_spec()

    sizing = rm.size(spec, balance=10000, sl_distance=0.00073, account_leverage=100)

    assert sizing.approved
    assert sizing.volume == 1.36
    assert sizing.risk_amount == 99.28
    assert sizing.target_risk_amount == 100.0


def test_position_sizing_rejects_minimum_volume_that_breaks_risk_limit():
    rm = RiskManager(risk_per_trade_pct=1.0, max_margin_per_trade_usd=5000)
    spec = eurusd_spec()

    sizing = rm.size(spec, balance=10000, sl_distance=0.13, account_leverage=100)

    assert not sizing.approved
    assert "1.25x" in sizing.reason


def test_position_sizing_uses_broker_margin_and_free_margin():
    rm = RiskManager(risk_per_trade_pct=1.0, max_margin_per_trade_usd=5000)
    spec = eurusd_spec()

    sizing = rm.size(
        spec,
        balance=10000,
        sl_distance=0.001,
        margin_estimator=lambda volume: 900.0,
        margin_free=800.0,
    )

    assert not sizing.approved
    assert "margen libre" in sizing.reason
 
 
def base_risk():
    return RiskConfig(
        risk_per_trade_pct=1.0, max_daily_loss_pct=3.0, max_drawdown_pct=10.0,
        max_trades_per_day=2, max_open_positions=1, min_confidence=60, max_spread_points=30,
    )
 
 
def test_guard_allows_when_ok():
    guard = RiskGuard(base_risk())
    guard.start_day(date(2026, 7, 17), 10000)
    d = guard.can_open_trade(date(2026, 7, 17), 10000, 10000, 0, 5, True)
    assert d.allowed
 
 
def test_guard_blocks_outside_session():
    guard = RiskGuard(base_risk())
    guard.start_day(date(2026, 7, 17), 10000)
    d = guard.can_open_trade(date(2026, 7, 17), 10000, 10000, 0, 5, False)
    assert not d.allowed
 
 
def test_guard_blocks_high_spread():
    guard = RiskGuard(base_risk())
    guard.start_day(date(2026, 7, 17), 10000)
    d = guard.can_open_trade(date(2026, 7, 17), 10000, 10000, 0, 40, True)
    assert not d.allowed
 
 
def test_guard_blocks_max_trades():
    guard = RiskGuard(base_risk())
    guard.start_day(date(2026, 7, 17), 10000)
    guard.register_trade_opened()
    guard.register_trade_opened()
    d = guard.can_open_trade(date(2026, 7, 17), 10000, 10000, 0, 5, True)
    assert not d.allowed
 
 
def test_guard_blocks_daily_loss():
    guard = RiskGuard(base_risk())
    guard.start_day(date(2026, 7, 17), 10000)
    guard.register_closed_pnl(-350)  # -3.5% > 3%
    d = guard.can_open_trade(date(2026, 7, 17), 10000, 9650, 0, 5, True)
    assert not d.allowed
 
 
def test_guard_blocks_drawdown():
    guard = RiskGuard(base_risk())
    guard.start_day(date(2026, 7, 17), 10000)
    guard.update_equity(10000)
    # equity cae 12% desde el pico
    d = guard.can_open_trade(date(2026, 7, 17), 10000, 8800, 0, 5, True)
    assert not d.allowed
 
 
def test_guard_resets_on_new_day():
    guard = RiskGuard(base_risk())
    guard.start_day(date(2026, 7, 17), 10000)
    guard.register_trade_opened()
    guard.register_trade_opened()
    # nuevo día -> se reinicia el conteo
    d = guard.can_open_trade(date(2026, 7, 18), 10000, 10000, 0, 5, True)
    assert d.allowed
    assert guard.trades_today == 0


def test_guard_persists_and_restores_state(tmp_path):
    store = TradeStore(str(tmp_path / "guard.db"))
    guard = RiskGuard(base_risk(), store=store, timezone_name="UTC")
    guard.start_day(date(2026, 7, 17), 10000)
    guard.register_trade_opened()
    guard.register_closed_pnl(-100)
    guard.update_equity(10500)

    restored = RiskGuard(base_risk(), store=store, timezone_name="UTC")
    restored.start_day(date(2026, 7, 17), 9900)

    assert restored.trades_today == 1
    assert restored.daily_loss_pct() == 1.0
    assert restored.drawdown_pct(10500) == 0.0
    store.close()


def test_guard_uses_session_timezone_and_ignores_previous_day_pnl(tmp_path):
    store = TradeStore(str(tmp_path / "guard.db"))
    guard = RiskGuard(base_risk(), store=store, timezone_name="America/Toronto")
    guard.start_day(date(2026, 7, 17), 10000)

    previous_day = datetime(2026, 7, 18, 4, 30, tzinfo=timezone.utc)
    guard.register_closed_pnl(-500, closed_at=previous_day)

    assert guard.daily_loss_pct() == 0.0
    store.close()


def test_guard_blocks_same_currency_exposure():
    guard = RiskGuard(base_risk())
    positions = [
        Position(1, "EURUSD", "BUY", 0.1, 1.1, 1.0, 1.2, 0.0),
    ]

    assert guard.currency_exposure_allowed("GBPUSD", "BUY", positions) is False
    assert guard.currency_exposure_allowed("USDJPY", "BUY", positions) is True