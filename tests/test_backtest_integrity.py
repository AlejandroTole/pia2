import pandas as pd

from pia2.backtesting.historical_backtest import simulate_exit


def test_simulate_exit_uses_next_candles_and_prioritizes_stop():
    frame = pd.DataFrame([
        {"time": pd.Timestamp("2026-01-01"), "high": 1.101, "low": 1.099, "close": 1.1},
        {"time": pd.Timestamp("2026-01-02"), "high": 1.105, "low": 1.095, "close": 1.1},
    ])

    exit_time, exit_price = simulate_exit(frame, 0, "BUY", 1.095, 1.105)

    assert exit_time == pd.Timestamp("2026-01-02").to_pydatetime()
    assert exit_price == 1.095