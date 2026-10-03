"""Tests de validación walk-forward multifold del backtest histórico."""

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from backtesting.historical_backtest import (
    load_feature_frame,
    run_scenario,
    run_walk_forward,
    simulate_exit,
)
from config.loader import load_config


def _make_frame(tmp_path, n_rows: int = 96) -> pd.DataFrame:
    rows = []
    base = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    price = 1.10000
    labels = ["BUY", "BUY", "SELL"]
    for index in range(n_rows):
        timestamp = base + timedelta(minutes=15 * index)
        open_price = price
        close = price + 0.00050
        rows.append({
            "time": timestamp.isoformat(),
            "open": open_price,
            "high": close + 0.00010,
            "low": open_price - 0.00010,
            "close": close,
            "RSI": 55.0,
            "ATR": 0.00200,
            "trend": "Alcista",
            "future_result": labels[index % 3],
        })
        price = close
    feature_path = tmp_path / "features.json"
    feature_path.write_text(json.dumps(rows), encoding="utf-8")
    return load_feature_frame(feature_path)


@pytest.fixture
def frame(tmp_path):
    return _make_frame(tmp_path)


@pytest.fixture
def config():
    loaded = load_config("config/config.example.yaml")
    return replace(loaded, risk=replace(loaded.risk, min_confidence=0))


def _run_wf(frame, config, **kwargs):
    return run_walk_forward(
        {"EURUSD": frame},
        config,
        50,
        10000.0,
        spread_points=20.0,
        train_ratio=0.5,
        **kwargs,
    )


def test_fold_windows_are_ordered_and_disjoint(frame, config):
    result = _run_wf(frame, config, n_folds=3)

    assert len(result.folds) == 3
    for previous, current in zip(result.folds, result.folds[1:]):
        assert previous.test_end < current.test_start
    assert result.total_trades == sum(fold.result.total_trades for fold in result.folds)
    assert result.wins == sum(fold.result.wins for fold in result.folds)
    assert result.losses == sum(fold.result.losses for fold in result.folds)
    assert result.net_profit == round(sum(fold.result.net_profit for fold in result.folds), 2)
    assert 0.0 <= result.max_drawdown_pct < 100.0
    assert result.folds_profitable == sum(
        1 for fold in result.folds if fold.result.net_profit > 0
    )


def test_trades_stay_inside_fold_test_windows(frame, config):
    result = _run_wf(frame, config, n_folds=3)

    assert result.total_trades > 0
    for fold in result.folds:
        start_day = fold.test_start.date()
        end_day = fold.test_end.date()
        for day_string in fold.result.trades_by_day or {}:
            trade_day = date.fromisoformat(day_string)
            assert start_day <= trade_day <= end_day


def test_single_fold_matches_classic_split(frame, config):
    walk_forward = _run_wf(frame, config, n_folds=1)
    classic = run_scenario(
        {"EURUSD": frame},
        config,
        50,
        10000.0,
        spread_points=20.0,
        train_ratio=0.5,
    )

    assert walk_forward.total_trades == classic.total_trades
    assert walk_forward.wins == classic.wins
    assert walk_forward.losses == classic.losses
    assert walk_forward.net_profit == classic.net_profit


def test_insufficient_oos_data_raises(config, tmp_path):
    small_frame = _make_frame(tmp_path, n_rows=12)

    with pytest.raises(ValueError, match="OOS insuficientes"):
        _run_wf(small_frame, config, n_folds=5)


def test_n_folds_must_be_positive(frame, config):
    with pytest.raises(ValueError, match="n_folds"):
        _run_wf(frame, config, n_folds=0)


def test_simulated_exit_does_not_read_past_fold_boundary(frame):
    boundary = frame.iloc[6]["time"].to_pydatetime()

    exit_time, exit_price = simulate_exit(
        frame,
        entry_index=2,
        direction="BUY",
        stop_loss=0.9,
        take_profit=2.0,
        test_until=boundary,
    )

    assert exit_time < boundary
    assert exit_price == float(frame.iloc[5]["close"])