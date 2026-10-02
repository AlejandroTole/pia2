from __future__ import annotations


class TimeFrameAgent:
    def analyze(self, symbol: str):
        return {
            "symbol": symbol,
            "direction": "BUY",
            "alignment": True,
            "score": 90,
        }
