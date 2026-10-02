"""Persistencia de noticias (actuales e históricas) en SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class NewsEvent:
    title: str
    source: str
    published_at: datetime
    impact: str = "MEDIUM"  # HIGH | MEDIUM | LOW
    sentiment: str = "NEUTRAL"  # BULLISH | BEARISH | NEUTRAL
    symbols: str = ""  # csv: EURUSD.PRO,GBPUSD.PRO
    url: str = ""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    impact TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    symbols TEXT,
    url TEXT,
    fingerprint TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_news_events_published_at ON news_events(published_at);
CREATE INDEX IF NOT EXISTS idx_news_events_impact ON news_events(impact);
"""


class NewsStore:
    def __init__(self, db_path: str = "data/runtime/news.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def upsert_events(self, events: list[NewsEvent]) -> int:
        inserted = 0
        for event in events:
            fp = self._fingerprint(event)
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO news_events
                (title, source, published_at, impact, sentiment, symbols, url, fingerprint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.title,
                    event.source,
                    event.published_at.astimezone(timezone.utc).isoformat(),
                    event.impact,
                    event.sentiment,
                    event.symbols,
                    event.url,
                    fp,
                ),
            )
            if cur.rowcount:
                inserted += 1
        self._conn.commit()
        return inserted

    def recent_events(self, since: datetime) -> list[NewsEvent]:
        rows = self._conn.execute(
            """
            SELECT title, source, published_at, impact, sentiment, symbols, url
            FROM news_events
            WHERE published_at >= ?
            ORDER BY published_at DESC
            """,
            (since.astimezone(timezone.utc).isoformat(),),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def events_between(self, start: datetime, end: datetime) -> list[NewsEvent]:
        rows = self._conn.execute(
            """
            SELECT title, source, published_at, impact, sentiment, symbols, url
            FROM news_events
            WHERE published_at BETWEEN ? AND ?
            ORDER BY published_at ASC
            """,
            (
                start.astimezone(timezone.utc).isoformat(),
                end.astimezone(timezone.utc).isoformat(),
            ),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def blocking_event(
        self,
        symbol: str,
        now_utc: datetime,
        high_before_min: int,
        high_after_min: int,
        medium_enabled: bool,
        med_before_min: int,
        med_after_min: int,
    ) -> NewsEvent | None:
        start = now_utc - timedelta(minutes=max(high_after_min, med_after_min))
        end = now_utc + timedelta(minutes=max(high_before_min, med_before_min))
        candidates = self.events_between(start, end)

        for event in candidates:
            if not self._matches_symbol(event.symbols, symbol):
                continue
            dt_min = (event.published_at.astimezone(timezone.utc) - now_utc).total_seconds() / 60.0
            impact = event.impact.upper()
            if impact == "HIGH":
                if -high_after_min <= dt_min <= high_before_min:
                    return event
            elif impact == "MEDIUM" and medium_enabled:
                if -med_after_min <= dt_min <= med_before_min:
                    return event
        return None

    @staticmethod
    def _fingerprint(event: NewsEvent) -> str:
        ts = int(event.published_at.astimezone(timezone.utc).timestamp())
        return f"{event.source}|{ts}|{event.title.strip().lower()}"

    @staticmethod
    def _matches_symbol(symbols_csv: str, symbol: str) -> bool:
        if not symbols_csv:
            return True
        symbols = {s.strip().upper() for s in symbols_csv.split(",") if s.strip()}
        return symbol.upper() in symbols

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> NewsEvent:
        dt = datetime.fromisoformat(row["published_at"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return NewsEvent(
            title=row["title"],
            source=row["source"],
            published_at=dt,
            impact=row["impact"],
            sentiment=row["sentiment"],
            symbols=row["symbols"] or "",
            url=row["url"] or "",
        )
