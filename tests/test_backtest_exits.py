"""Tests del motivo de salida del backtest (TP/SL/TIMEOUT)."""

import pandas as pd

from backtesting.historical_backtest import simulate_exit


def _frame(highs, lows, closes):
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=len(closes), freq="15min", tz="UTC"),
        "high": highs,
        "low": lows,
        "close": closes,
    })


def test_exit_tp():
    frame = _frame(
        [1.1010, 1.1030],
        [1.0990, 1.0995],
        [1.1000, 1.1020],
    )

    _, price, reason = simulate_exit(
        frame, 0, "BUY", stop_loss=1.0980, take_profit=1.1025
    )

    assert reason == "TP" and price == 1.1025


def test_exit_sl_priority_on_tie():
    frame = _frame(
        [1.1000, 1.1030],
        [1.0990, 1.0970],
        [1.1000, 1.1000],
    )

    _, price, reason = simulate_exit(
        frame, 0, "BUY", stop_loss=1.0980, take_profit=1.1025
    )

    assert reason == "SL" and price == 1.0980


def test_exit_timeout():
    frame = _frame(
        [1.1010] * 5,
        [1.0990] * 5,
        [1.1000] * 5,
    )

    _, price, reason = simulate_exit(
        frame, 0, "BUY", stop_loss=1.0980, take_profit=1.1025
    )

    assert reason == "TIMEOUT" and price == 1.1000