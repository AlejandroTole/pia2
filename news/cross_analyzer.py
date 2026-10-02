"""Cruce de noticias contra velas/precio históricos descargados (M15)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pia2.news.store import NewsEvent


class NewsCrossAnalyzer:
    def __init__(self, features_folder: str = "data/historical/features"):
        self.features_folder = Path(features_folder)
        self._cache: dict[str, list[dict]] = {}

    def summarize_for_symbol(
        self,
        symbol: str,
        events: list[NewsEvent],
        windows_minutes: list[int],
        min_events: int,
    ) -> dict:
        series = self._load_series(symbol)
        if not series or not events:
            return self._empty_summary()

        usable = [e for e in events if self._matches_symbol(e, symbol)]
        if not usable:
            return self._empty_summary()

        reactions_by_window: dict[int, list[float]] = {w: [] for w in windows_minutes}
        high_count = 0
        medium_count = 0

        for event in usable:
            idx = self._find_first_index(series, event.published_at)
            if idx is None:
                continue
            if event.impact == "HIGH":
                high_count += 1
            elif event.impact == "MEDIUM":
                medium_count += 1

            for minutes in windows_minutes:
                step = max(1, int(minutes / 15))
                j = idx + step
                if j >= len(series):
                    continue
                start = float(series[idx]["close"])
                end = float(series[j]["close"])
                if start:
                    reactions_by_window[minutes].append((end - start) / start)

        # Regla simple de sesgo: usar ventana media (si existe), o la primera.
        chosen_window = windows_minutes[1] if len(windows_minutes) > 1 else windows_minutes[0]
        returns = reactions_by_window.get(chosen_window, [])
        sample = len(returns)
        if sample < min_events:
            return {
                **self._empty_summary(),
                "events_used": sample,
                "high_events": high_count,
                "medium_events": medium_count,
                "summary": (
                    f"Noticias: muestra insuficiente ({sample}/{min_events}) para sesgo robusto"
                ),
            }

        avg = sum(returns) / sample if sample else 0.0
        up = sum(1 for r in returns if r > 0)
        down = sum(1 for r in returns if r < 0)
        bias = "BUY" if up > down else ("SELL" if down > up else "NEUTRAL")
        confidence = min(100.0, abs(up - down) / sample * 100.0)

        by_window = {
            str(w): round((sum(vals) / len(vals)) * 100, 4) if vals else 0.0
            for w, vals in reactions_by_window.items()
        }

        return {
            "bias": bias,
            "confidence": round(confidence, 2),
            "events_used": sample,
            "high_events": high_count,
            "medium_events": medium_count,
            "avg_move_pct_by_window": by_window,
            "summary": (
                f"Noticias históricas ({sample}): sesgo {bias}, confianza {round(confidence, 2)}%"
            ),
        }

    def _load_series(self, symbol: str) -> list[dict]:
        if symbol in self._cache:
            return self._cache[symbol]

        path = self.features_folder / f"{symbol}.json"
        if not path.exists():
            self._cache[symbol] = []
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._cache[symbol] = []
            return []

        # Se ordena por tiempo por seguridad.
        data.sort(key=lambda x: x.get("time", ""))
        self._cache[symbol] = data
        return data

    @staticmethod
    def _find_first_index(series: list[dict], event_time: datetime) -> int | None:
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        lo, hi = 0, len(series) - 1
        out = None
        while lo <= hi:
            mid = (lo + hi) // 2
            t = _parse_series_time(series[mid].get("time", ""))
            if t >= event_time:
                out = mid
                hi = mid - 1
            else:
                lo = mid + 1
        return out

    @staticmethod
    def _matches_symbol(event: NewsEvent, symbol: str) -> bool:
        if not event.symbols:
            return True
        symbols = {x.strip().upper() for x in event.symbols.split(",") if x.strip()}
        return symbol.upper() in symbols

    @staticmethod
    def _empty_summary() -> dict:
        return {
            "bias": "NEUTRAL",
            "confidence": 0.0,
            "events_used": 0,
            "high_events": 0,
            "medium_events": 0,
            "avg_move_pct_by_window": {},
            "summary": "Sin datos de noticias suficientes.",
        }


def _parse_series_time(value: str) -> datetime:
    # Formato esperado del histórico: "YYYY-mm-dd HH:MM:SS"
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        dt = datetime(1970, 1, 1)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
