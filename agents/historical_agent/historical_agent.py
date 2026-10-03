from __future__ import annotations

from typing import Any

from .feature_builder import HistoricalFeatureBuilder
from .historical_intelligence import HistoricalIntelligence


class HistoricalAgent:
    def __init__(self):
        self.feature_builder = HistoricalFeatureBuilder()
        self.intelligence = HistoricalIntelligence()

    def build_memory(self, symbol: str, timeframe, candles: int = 50000):
        try:
            from .multi_historical_builder import MultiHistoricalBuilder
            builder = MultiHistoricalBuilder(output_folder=self.feature_builder.output_folder)
            try:
                return builder.download_symbol(symbol, candles=candles)
            except Exception:
                data = self.feature_builder.build(symbol=symbol, candles=candles)
                return data
        except Exception:
            data = self.feature_builder.build(symbol=symbol, candles=candles)
            return data

    def analyze(self, market_data: dict[str, Any]):
        return self.intelligence.analyze(market_data)
