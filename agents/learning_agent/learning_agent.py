from __future__ import annotations

from memory.memory_manager import MemoryManager


class LearningAgent:
    def __init__(self):
        self.memory = MemoryManager()

    def analyze_performance(self, symbol: str | None = None):
        stats = self.memory.statistics()
        if symbol:
            trades = self.memory.search_symbol(symbol)
            if trades:
                stats["symbol_trades"] = len(trades)
        return stats
