"""Tests de paridad backtest/live (backtesting/historical_backtest.py).

Cubren:
- effective_spread: la columna "spread" de la fila manda si > 0; si no,
  se usa el default de CLI/config (antes el parámetro se sobrescribía
  siempre y quedaba inútil).
- min_confidence: el backtest respeta el umbral de la config, como el live.
- block_symbol_stacking: sin apilamiento por símbolo, como el live.
- cooldown post-loss: tras una pérdida no se opera el par por N minutos.
- maybe_close_trades registra la hora real de cierre de la pérdida.
"""

import json
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from backtesting.historical_backtest import (
    OpenTrade,
    SymbolStats,
    effective_spread,
    load_feature_frame,
    maybe_close_trades,
    run_scenario,
)
from config.loader import load_config
from pia2.risk.risk_guard import RiskGuard


# ---------------------------------------------------------------------------
# effective_spread
# ---------------------------------------------------------------------------

def test_effective_spread_row_value_wins():
    row = pd.Series({"spread": 15.0})
    assert effective_spread(row, 20.0) == 15.0


def test_effective_spread_falls_back_to_default():
    assert effective_spread(pd.Series({}), 20.0) == 20.0
    assert effective_spread(pd.Series({"spread": 0.0}), 20.0) == 20.0
    assert effective_spread(pd.Series({"spread": -5.0}), 20.0) == 20.0
    assert effective_spread(pd.Series({"spread": ""}), 20.0) == 20.0
    assert effective_spread(pd.Series({"spread": "no-numérico"}), 20.0) == 20.0
    assert effective_spread(pd.Series({"spread": None}), 20.0) == 20.0


# ---------------------------------------------------------------------------
# Escenario sintético compartido
# ---------------------------------------------------------------------------

def _make_frame(path: Path, n=48, drift=0.00050, seed=7) -> pd.DataFrame:
    """48 velas M15 un lunes dentro de la sesión de ejemplo.

    Tendencia "Alcista" y RSI 55 constantes; future_result mezclado
    BUY/BUY/SELL -> confianza de la señal ~= 33.3.
    """
    import random
    random.seed(seed)
    rows = []
    base = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)  # lunes
    price = 1.10000
    labels = ["BUY", "BUY", "SELL"]
    for i in range(n):
        t = base + timedelta(minutes=15 * i)
        o = price
        c = price + drift + random.uniform(-0.0003, 0.0003)
        rows.append({
            "time": t.isoformat(),
            "open": o,
            "high": max(o, c) + 0.00010,
            "low": min(o, c) - 0.00010,
            "close": c,
            "RSI": 55.0,
            "ATR": 0.00200,
            "trend": "Alcista",
            "future_result": labels[i % 3],
        })
        price = c
    frame_path = path / "features.json"
    frame_path.write_text(json.dumps(rows), encoding="utf-8")
    return load_feature_frame(frame_path)


@pytest.fixture
def rising_frame(tmp_path):
    return _make_frame(tmp_path, drift=0.00050)


@pytest.fixture
def falling_frame(tmp_path):
    # Precios a la baja pero señal BUY -> las operaciones pierden.
    return _make_frame(tmp_path, drift=-0.00050)


@pytest.fixture
def base_config():
    return load_config("config/config.example.yaml")


def _run(frame, config, **risk_overrides):
    cfg = replace(config, risk=replace(config.risk, **risk_overrides))
    return run_scenario(
        {"EURUSD": frame},
        cfg,
        max_trades_per_day=50,
        starting_balance=10000.0,
        spread_points=20.0,
        train_ratio=0.5,
    )


# ---------------------------------------------------------------------------
# Gates de paridad
# ---------------------------------------------------------------------------

def test_min_confidence_gate_blocks_threshold_above_confidence_ceiling(rising_frame, base_config):
    open_gate = _run(rising_frame, base_config, min_confidence=0)
    closed_gate = _run(rising_frame, base_config, min_confidence=100.01)
    assert open_gate.total_trades > 0
    assert closed_gate.total_trades < open_gate.total_trades


def test_symbol_stacking_gate_limits_trades(falling_frame, base_config):
    stacked = _run(
        falling_frame, base_config, min_confidence=0,
        block_symbol_stacking=True, max_open_positions=5,
        cooldown_minutes_after_loss=0,
    )
    unstacked = _run(
        falling_frame, base_config, min_confidence=0,
        block_symbol_stacking=False, max_open_positions=5,
        cooldown_minutes_after_loss=0,
    )
    assert unstacked.total_trades > stacked.total_trades


def test_cooldown_after_loss_reduces_trades(falling_frame, base_config):
    no_cooldown = _run(
        falling_frame, base_config, min_confidence=0,
        block_symbol_stacking=False, max_open_positions=5,
        cooldown_minutes_after_loss=0,
    )
    with_cooldown = _run(
        falling_frame, base_config, min_confidence=0,
        block_symbol_stacking=False, max_open_positions=5,
        cooldown_minutes_after_loss=240,
    )
    assert no_cooldown.losses > 0  # el escenario realmente genera pérdidas
    assert with_cooldown.total_trades < no_cooldown.total_trades


def test_maybe_close_trades_records_loss_time():
    now = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)
    exit_time = now - timedelta(minutes=15)
    loser = OpenTrade(
        symbol="EURUSD", direction="BUY", entry_time=exit_time - timedelta(hours=1),
        exit_time=exit_time, entry_price=1.1000, exit_price=1.0990,
        stop_loss=1.0980, take_profit=1.1040, volume=0.01, profit=-10.0,
    )
    winner = OpenTrade(
        symbol="EURUSD", direction="BUY", entry_time=exit_time - timedelta(hours=1),
        exit_time=exit_time, entry_price=1.1000, exit_price=1.1020,
        stop_loss=1.0980, take_profit=1.1040, volume=0.01, profit=20.0,
    )
    cfg = load_config("config/config.example.yaml")
    guard = RiskGuard(cfg.risk)
    stats = {"EURUSD": SymbolStats()}
    last_loss: dict = {}
    remaining, _ = maybe_close_trades(
        [loser, winner], now, 10000.0, guard, stats, [], last_loss_time=last_loss
    )
    assert remaining == []
    # Solo la pérdida registra hora de cierre (la ganancia no).
    assert last_loss == {("EURUSD", "BUY"): exit_time}
    assert stats["EURUSD"].losses == 1
    assert stats["EURUSD"].wins == 1
