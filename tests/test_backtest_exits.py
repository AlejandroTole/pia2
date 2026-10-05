"""Tests del motivo de salida del backtest (TP/SL/BE/TIMEOUT)."""

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
        frame, 0, "BUY", 1.1000, stop_loss=1.0980, take_profit=1.1025
    )

    assert reason == "TP" and price == 1.1025


def test_exit_sl_priority_on_tie():
    frame = _frame(
        [1.1000, 1.1030],
        [1.0990, 1.0970],
        [1.1000, 1.1000],
    )

    _, price, reason = simulate_exit(
        frame, 0, "BUY", 1.1000, stop_loss=1.0980, take_profit=1.1025
    )

    assert reason == "SL" and price == 1.0980


def test_exit_timeout():
    frame = _frame(
        [1.1010] * 5,
        [1.0990] * 5,
        [1.1000] * 5,
    )

    _, price, reason = simulate_exit(
        frame, 0, "BUY", 1.1000, stop_loss=1.0980, take_profit=1.1025
    )

    assert reason == "TIMEOUT" and price == 1.1000


def test_breakeven_arms_and_exits():
    frame = _frame(
        [1.1005, 1.1025, 1.1010],
        [1.0995, 1.0990, 1.0995],
        [1.1000, 1.1015, 1.1002],
    )

    _, price, reason = simulate_exit(
        frame,
        0,
        "BUY",
        1.1000,
        stop_loss=1.0960,
        take_profit=1.1040,
        breakeven_atr_mult=1.0,
        atr=0.0020,
    )

    assert reason == "BE" and price == 1.1000


def test_breakeven_not_armed_without_excursion():
    frame = _frame(
        [1.1005, 1.0990],
        [1.0995, 1.0950],
        [1.1000, 1.0960],
    )

    _, price, reason = simulate_exit(
        frame,
        0,
        "BUY",
        1.1000,
        stop_loss=1.0960,
        take_profit=1.1040,
        breakeven_atr_mult=1.0,
        atr=0.0020,
    )

    assert reason == "SL" and price == 1.0960


def test_breakeven_off_by_default():
    frame = _frame(
        [1.1005, 1.1025, 1.1010],
        [1.0995, 1.0990, 1.0995],
        [1.1000, 1.1015, 1.1002],
    )

    _, _, reason = simulate_exit(
        frame,
        0,
        "BUY",
        1.1000,
        stop_loss=1.0960,
        take_profit=1.1040,
    )

    assert reason == "TIMEOUT"


def test_breakeven_sell_arms_and_exits():
    frame = _frame(
        [1.1005, 1.1010, 1.1010],
        [1.0995, 1.0975, 1.0995],
        [1.1000, 1.0985, 1.1000],
    )

    _, price, reason = simulate_exit(
        frame,
        0,
        "SELL",
        1.1000,
        stop_loss=1.1040,
        take_profit=1.0960,
        breakeven_atr_mult=1.0,
        atr=0.0020,
    )

    assert reason == "BE" and price == 1.1000


def test_original_stop_wins_before_breakeven_arms_on_same_candle():
    frame = _frame(
        [1.1005, 1.1025],
        [1.0995, 1.0950],
        [1.1000, 1.1000],
    )

    _, price, reason = simulate_exit(
        frame,
        0,
        "BUY",
        1.1000,
        stop_loss=1.0960,
        take_profit=1.1040,
        breakeven_atr_mult=1.0,
        atr=0.0020,
    )

    assert reason == "SL" and price == 1.0960


def test_trail_activates_and_exits():
    frame = _frame(
        [1.1005, 1.1030, 1.1020],
        [1.0995, 1.1015, 1.1005],
        [1.1000, 1.1025, 1.1010],
    )

    _, price, reason = simulate_exit(
        frame,
        0,
        "BUY",
        1.1000,
        stop_loss=1.0960,
        take_profit=1.1040,
        trail_atr_mult=1.0,
        atr=0.0020,
    )

    assert reason == "TRAIL" and price == 1.1010


def test_trail_inactive_without_excursion():
    frame = _frame(
        [1.1005, 1.1008],
        [1.0995, 1.0950],
        [1.1000, 1.0960],
    )

    _, price, reason = simulate_exit(
        frame,
        0,
        "BUY",
        1.1000,
        stop_loss=1.0960,
        take_profit=1.1040,
        trail_atr_mult=1.0,
        atr=0.0020,
    )

    assert reason == "SL" and price == 1.0960


def test_trail_never_moves_against():
    frame = _frame(
        [1.1005, 1.1030, 1.1015, 1.1025],
        [1.0995, 1.1015, 1.1000, 1.1012],
        [1.1000, 1.1025, 1.1010, 1.1020],
    )

    _, price, reason = simulate_exit(
        frame,
        0,
        "BUY",
        1.1000,
        stop_loss=1.0960,
        take_profit=1.1040,
        trail_atr_mult=1.0,
        atr=0.0020,
    )

    assert reason == "TRAIL" and price == 1.1010