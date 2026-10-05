import sys
from dataclasses import replace

from backtesting.historical_backtest import parse_args
from config.loader import load_config


def test_parse_args_min_confidence(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["historical_backtest", "--min-confidence", "80"])
    assert parse_args().min_confidence == 80.0

    monkeypatch.setattr(sys, "argv", ["historical_backtest"])
    assert parse_args().min_confidence is None


def test_config_min_confidence_override():
    config = load_config("config/config.example.yaml")
    config = replace(config, risk=replace(config.risk, min_confidence=80))

    assert config.risk.min_confidence == 80