from __future__ import annotations

from memory.memory_manager import MemoryManager


class MemoryAgent:
    def __init__(self):
        self.memory = MemoryManager()

    def analyze(self, market_situation: dict):
        symbol = market_situation.get("symbol", "UNKNOWN")
        signal = market_situation.get("signal", "WAIT")
        confidence = float(market_situation.get("confidence", 0))

        signal_matches = self.memory.search_signal(signal)
        recent_entries = self.memory.recent(5)

        return {
            "symbol": symbol,
            "signal": signal,
            "confidence": confidence,
            "signal_matches": len(signal_matches),
            "recent_entries": recent_entries,
            "status": "OK",
        }
