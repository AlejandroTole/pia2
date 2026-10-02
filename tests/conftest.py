import pandas as pd
import pytest
 
from config.schema import (
    IndicatorsConfig,
    PIAConfig,
    RiskConfig,
    ScheduleConfig,
    Session,
)
from pia2.market.instruments import SymbolSpec
 
 
@pytest.fixture
def eurusd_spec():
    return SymbolSpec(
        name="EURUSD", digits=5, point=0.00001, tick_size=0.00001, tick_value=1.0,
        contract_size=100000, volume_min=0.01, volume_max=100, volume_step=0.01,
    )
 
 
@pytest.fixture
def always_on_config():
    """Config demo con horario siempre abierto (para tests de flujo)."""
    return PIAConfig(
        mode="demo",
        symbols=["EURUSD"],
        symbol_suffix="",
        timeframe="M15",
        candles=300,
        risk=RiskConfig(
            risk_per_trade_pct=1.0, max_daily_loss_pct=3.0, max_drawdown_pct=10.0,
            max_trades_per_day=4, max_open_positions=2, min_confidence=60, max_spread_points=50,
        ),
        indicators=IndicatorsConfig(ema_fast=50, ema_slow=200, rsi_period=14, atr_period=14,
                                    atr_sl_multiplier=2.0, atr_tp_multiplier=4.0),
        schedule=ScheduleConfig(
            timezone="UTC",
            sessions=[Session("00:00", "23:59")],
            trade_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        ),
    )
 
 
@pytest.fixture
def uptrend_candles():
    """250 velas en tendencia alcista, con high/low para ATR."""
    n = 250
    rows = []
    price = 1.00000
    base_time = pd.Timestamp("2026-07-01 00:00:00")
    for i in range(n):
        price += 0.0005
        rows.append({
            "time": base_time + pd.Timedelta(minutes=15 * i),
            "open": price - 0.0003,
            "high": price + 0.0010,
            "low": price - 0.0010,
            "close": price,
            "volume": 100,
        })
    return pd.DataFrame(rows)