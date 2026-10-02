from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd

from pia2.agents.historical_agent.multi_historical_builder import MultiHistoricalBuilder


class HistoricalFeatureBuilder:
    def __init__(self, output_folder: str = "data/historical/features"):
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
        self.builder = MultiHistoricalBuilder(output_folder=output_folder)

    def build(self, symbol: str | None = None, candles: int = 500):
        if symbol is None:
            symbol = "GBPUSD.PRO"

        path = os.path.join(self.output_folder, f"{symbol}.json")
        if not os.path.exists(path):
            sample = [
                {
                    "symbol": symbol,
                    "time": "2024-01-01T00:00:00",
                    "close": 1.0,
                    "RSI": 50,
                    "ATR": 0.0001,
                    "trend": "Alcista",
                    "future_move": 0.0002,
                    "future_result": "BUY",
                }
            ]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sample, f)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        return data
