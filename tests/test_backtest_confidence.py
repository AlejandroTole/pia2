"""Tests de la calibración de confianza del backtest (z-score del margen de votos)."""

from backtesting.historical_backtest import (
    PatternRuntimeIndex,
    SymbolStats,
    build_signal_from_counts,
)
from config.loader import load_config


def _config():
    return load_config("config/config.example.yaml")


def _index_with(buys: int, sells: int, trend: str = "Alcista", rsi: float = 55.0):
    index = PatternRuntimeIndex(tolerance=10.0)
    for _ in range(buys):
        index.add(trend, rsi, "BUY")
    for _ in range(sells):
        index.add(trend, rsi, "SELL")
    return index


def test_balanced_votes_give_low_confidence():
    config = _config()
    index = _index_with(buys=1000, sells=1000)

    decision = build_signal_from_counts("Alcista", 55.0, SymbolStats(), config, index)

    assert decision.confidence < config.risk.min_confidence


def test_strong_edge_passes_min_confidence():
    config = _config()
    index = _index_with(buys=350, sells=150)

    decision = build_signal_from_counts("Alcista", 55.0, SymbolStats(), config, index)

    assert decision.signal == "BUY"
    assert decision.confidence >= config.risk.min_confidence


def test_weak_margin_with_huge_sample_stays_below_threshold():
    config = _config()
    index = _index_with(buys=5030, sells=4970)

    decision = build_signal_from_counts("Alcista", 55.0, SymbolStats(), config, index)

    assert decision.confidence < config.risk.min_confidence


def test_insufficient_patterns_returns_no_signal():
    config = _config()
    index = _index_with(buys=5, sells=5)

    decision = build_signal_from_counts("Alcista", 55.0, SymbolStats(), config, index)

    assert decision.signal not in {"BUY", "SELL"}