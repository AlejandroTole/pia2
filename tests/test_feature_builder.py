"""Tests del constructor de features históricos (agents/historical_agent)."""

import json

from agents.historical_agent.feature_builder import HistoricalFeatureBuilder
from config.loader import load_config


def test_build_creates_sample_when_folder_empty(tmp_path):
	config = load_config("config/config.example.yaml")
	builder = HistoricalFeatureBuilder(output_folder=str(tmp_path), config=config)

	result = builder.build()

	assert isinstance(result, list)
	assert len(result) > 0
	first = result[0]
	assert first["symbol"] == "GBPUSD.PRO"
	assert {"time", "close", "RSI", "ATR", "trend", "future_result"} <= set(first)


def test_build_reads_existing_file(tmp_path):
	config = load_config("config/config.example.yaml")
	sample = [{
		"symbol": "EURUSD",
		"time": "2024-01-01T00:00:00",
		"close": 1.1,
		"RSI": 55,
		"ATR": 0.0001,
		"trend": "Alcista",
		"future_result": "BUY",
	}]
	(tmp_path / "EURUSD.json").write_text(json.dumps(sample), encoding="utf-8")

	builder = HistoricalFeatureBuilder(output_folder=str(tmp_path), config=config)
	result = builder.build(symbol="EURUSD")

	assert result == sample