from types import SimpleNamespace

import pandas as pd

from pia2.backtesting.historical_backtest import PatternRuntimeIndex
from pia2.brokers.mt5_broker import MT5Broker
from pia2.core.reconciler import _find_exit
from pia2.memory.store import TradeRecord


class CandleMT5:
    TIMEFRAME_M15 = "M15"

    def __init__(self):
        self.args = None

    def copy_rates_from_pos(self, *args):
        self.args = args
        return [{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1}]


def test_mt5_candle_download_skips_open_bar():
    broker = MT5Broker()
    fake = CandleMT5()
    broker._mt5 = fake
    broker._timeframe = lambda timeframe: timeframe

    broker.get_candles("EURUSD", "M15", 10)

    assert fake.args[2] == 1


def test_pattern_index_does_not_use_current_row_result():
    index = PatternRuntimeIndex(tolerance=0)
    rows = [
        {"trend": "Alcista", "RSI": 50, "future_result": "BUY"},
        {"trend": "Alcista", "RSI": 50, "future_result": "SELL"},
    ]

    # Antes de que transcurran cuatro barras no hay patrón maduro disponible.
    for current_index in range(4):
        if current_index >= 4:
            row = rows[current_index - 4]
            index.add(row["trend"], row["RSI"], row["future_result"])

    assert index.counts("Alcista", 50) == (0, 0, 0)


def test_find_exit_uses_dataframe_without_name_error():
    trade = TradeRecord(
        symbol="EURUSD", direction="BUY", confidence=80, entry_price=1.1,
        stop_loss=1.09, take_profit=1.11, volume=1,
    )
    frame = pd.DataFrame([{"time": pd.Timestamp("2026-01-02"), "high": 1.12, "low": 1.1}])

    assert _find_exit(frame, trade) == 1.11