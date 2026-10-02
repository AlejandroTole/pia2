from __future__ import annotations

from memory.memory_manager import MemoryManager


class OpportunityScanner:
    def __init__(self):
        self.memory = MemoryManager()

    def scan(self, symbols):
        results = []
        for symbol in symbols:
            trades = self.memory.search_symbol(symbol)
            score = 50 + min(len(trades) * 5, 35)
            results.append({
                "symbol": symbol,
                "score": score,
                "trade_count": len(trades),
                "signal": "BUY" if score >= 60 else "WAIT",
            })
        return results
