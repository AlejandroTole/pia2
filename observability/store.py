"""Persistencia de observabilidad para señales, órdenes y snapshots de cuenta."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    features TEXT NOT NULL,
    raw_llm_response TEXT,
    decision TEXT,
    block_filter TEXT,
    latency_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals(symbol, observed_at);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    volume REAL NOT NULL,
    price REAL,
    spread_points REAL,
    status TEXT NOT NULL,
    comment TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_symbol_time ON orders(symbol, observed_at);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    balance REAL NOT NULL,
    equity REAL NOT NULL,
    margin_free REAL NOT NULL,
    margin_level REAL NOT NULL,
    open_positions INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_account_snapshots_symbol_time ON account_snapshots(symbol, observed_at);
"""


class ObservabilityStore:
    def __init__(self, db_path: str = "data/runtime/observability.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record_signal(
        self,
        symbol: str,
        timestamp: datetime,
        features: dict,
        raw_llm_response: str,
        decision: str,
        block_filter: str | None = None,
        latency_ms: int = 0,
    ) -> int:
        timestamp_str = _dt_to_utc_iso(timestamp)
        cur = self._conn.execute(
            """
            INSERT INTO signals (observed_at, symbol, features, raw_llm_response, decision, block_filter, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp_str,
                symbol,
                json.dumps(features, ensure_ascii=False),
                raw_llm_response,
                decision,
                block_filter,
                latency_ms,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def recent_signals(self, symbol: str | None = None, limit: int = 20) -> list[dict]:
        query = "SELECT * FROM signals"
        params: list = []
        if symbol is not None:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += " ORDER BY observed_at DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def record_order(
        self,
        symbol: str,
        timestamp: datetime,
        direction: str,
        volume: float,
        price: float | None,
        spread_points: float | None,
        status: str,
        comment: str | None = None,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO orders (observed_at, symbol, direction, volume, price, spread_points, status, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _dt_to_utc_iso(timestamp),
                symbol,
                direction,
                volume,
                price,
                spread_points,
                status,
                comment,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def recent_orders(self, symbol: str | None = None, limit: int = 20) -> list[dict]:
        query = "SELECT * FROM orders"
        params: list = []
        if symbol is not None:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += " ORDER BY observed_at DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def record_account_snapshot(
        self,
        timestamp: datetime,
        symbol: str,
        balance: float,
        equity: float,
        margin_free: float,
        margin_level: float,
        open_positions: int,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO account_snapshots
                (observed_at, symbol, balance, equity, margin_free, margin_level, open_positions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _dt_to_utc_iso(timestamp),
                symbol,
                balance,
                equity,
                margin_free,
                margin_level,
                open_positions,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def recent_account_snapshots(self, symbol: str | None = None, limit: int = 20) -> list[dict]:
        query = "SELECT * FROM account_snapshots"
        params: list = []
        if symbol is not None:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += " ORDER BY observed_at DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]


def _dt_to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")
