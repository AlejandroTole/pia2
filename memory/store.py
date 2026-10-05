"""Almacenamiento de operaciones en SQLite, con contexto y resultado real.
 
Cada operación se guarda con TODO el contexto que llevó a la decisión (señal,
confianza, razón del LLM, indicadores) y luego se actualiza con su resultado
REAL (WIN/LOSS, P/L en dinero) cuando el broker la cierra. Este historial
fiable es la base del aprendizaje.
"""
 
from __future__ import annotations
 
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
 
 
@dataclass
class TradeRecord:
    symbol: str
    direction: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    reason: str = ""
    context: dict = field(default_factory=dict)
    ticket: int | None = None
    status: str = "PENDING"  # PENDING | WIN | LOSS | BREAKEVEN | UNKNOWN
    exit_price: float = 0.0
    profit: float = 0.0
    opened_at: str = ""
    closed_at: str = ""
    id: int | None = None
 
 
_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence REAL,
    entry_price REAL,
    stop_loss REAL,
    take_profit REAL,
    volume REAL,
    reason TEXT,
    context TEXT,
    ticket INTEGER,
    status TEXT DEFAULT 'PENDING',
    exit_price REAL DEFAULT 0,
    profit REAL DEFAULT 0,
    opened_at TEXT,
    closed_at TEXT
);
CREATE TABLE IF NOT EXISTS guard_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    day TEXT,
    day_start_balance REAL NOT NULL DEFAULT 0,
    realized_pnl_today REAL NOT NULL DEFAULT 0,
    trades_today INTEGER NOT NULL DEFAULT 0,
    peak_equity REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS position_flags (
    ticket INTEGER PRIMARY KEY,
    be_armed INTEGER NOT NULL DEFAULT 0
);
"""
 
 
class TradeStore:
    def __init__(self, db_path: str = "data/runtime/pia.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
 
    def close(self) -> None:
        self._conn.close()

    def load_guard_state(self) -> dict | None:
        row = self._conn.execute(
            "SELECT day, day_start_balance, realized_pnl_today, trades_today, peak_equity "
            "FROM guard_state WHERE id = 1"
        ).fetchone()
        return dict(row) if row is not None else None

    def save_guard_state(
        self,
        day: str | None,
        day_start_balance: float,
        realized_pnl_today: float,
        trades_today: int,
        peak_equity: float,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO guard_state
                (id, day, day_start_balance, realized_pnl_today, trades_today, peak_equity)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                day=excluded.day,
                day_start_balance=excluded.day_start_balance,
                realized_pnl_today=excluded.realized_pnl_today,
                trades_today=excluded.trades_today,
                peak_equity=excluded.peak_equity
            """,
            (day, day_start_balance, realized_pnl_today, trades_today, peak_equity),
        )
        self._conn.commit()
 
    def save_decision(self, record: TradeRecord) -> int:
        opened_at = record.opened_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur = self._conn.execute(
            """
            INSERT INTO trades (symbol, direction, confidence, entry_price, stop_loss,
                take_profit, volume, reason, context, ticket, status, opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.symbol,
                record.direction,
                record.confidence,
                record.entry_price,
                record.stop_loss,
                record.take_profit,
                record.volume,
                record.reason,
                json.dumps(record.context, ensure_ascii=False),
                record.ticket,
                record.status,
                opened_at,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)
 
    def update_result_by_ticket(
        self, ticket: int, status: str, exit_price: float, profit: float,
        closed_at: str | None = None,
    ) -> bool:
        closed_at = closed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur = self._conn.execute(
            """
            UPDATE trades SET status = ?, exit_price = ?, profit = ?, closed_at = ?
            WHERE ticket = ? AND status = 'PENDING'
            """,
            (status, exit_price, profit, closed_at, ticket),
        )
        self._conn.commit()
        return cur.rowcount > 0
 
    def update_result_by_id(
        self, trade_id: int, status: str, exit_price: float, profit: float,
        closed_at: str | None = None,
    ) -> bool:
        closed_at = closed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur = self._conn.execute(
            """
            UPDATE trades SET status = ?, exit_price = ?, profit = ?, closed_at = ?
            WHERE id = ? AND status = 'PENDING'
            """,
            (status, exit_price, profit, closed_at, trade_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def mark_unknown_by_ticket(self, ticket: int) -> bool:
        cur = self._conn.execute(
            "UPDATE trades SET status = 'UNKNOWN' WHERE ticket = ? AND status = 'PENDING'",
            (ticket,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def is_be_armed(self, ticket: int) -> bool:
        row = self._conn.execute(
            "SELECT be_armed FROM position_flags WHERE ticket = ?",
            (ticket,),
        ).fetchone()
        return bool(row["be_armed"]) if row is not None else False

    def mark_be_armed(self, ticket: int) -> None:
        self._conn.execute(
            """
            INSERT INTO position_flags (ticket, be_armed) VALUES (?, 1)
            ON CONFLICT(ticket) DO UPDATE SET be_armed = 1
            """,
            (ticket,),
        )
        self._conn.commit()
 
    def pending(self, symbol: str | None = None) -> list[TradeRecord]:
        query = "SELECT * FROM trades WHERE status = 'PENDING'"
        params: tuple = ()
        if symbol is not None:
            query += " AND symbol = ?"
            params = (symbol,)
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_record(r) for r in rows]
 
    def closed(self, symbol: str | None = None) -> list[TradeRecord]:
        query = "SELECT * FROM trades WHERE status IN ('WIN', 'LOSS', 'BREAKEVEN')"
        params: tuple = ()
        if symbol is not None:
            query += " AND symbol = ?"
            params = (symbol,)
        query += " ORDER BY id"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_record(r) for r in rows]
 
    def recent_losers(self, limit: int = 20, symbol: str | None = None) -> list[TradeRecord]:
        query = "SELECT * FROM trades WHERE status = 'LOSS'"
        params: list = []
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_record(r) for r in rows]

    def latest_closed(self, symbol: str, direction: str | None = None) -> TradeRecord | None:
        query = (
            "SELECT * FROM trades WHERE symbol = ? "
            "AND status IN ('WIN', 'LOSS', 'BREAKEVEN') "
            "AND closed_at IS NOT NULL "
        )
        params: list = [symbol]
        if direction is not None:
            query += "AND direction = ? "
            params.append(direction)
        query += "ORDER BY closed_at DESC, id DESC LIMIT 1"
        row = self._conn.execute(query, tuple(params)).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)
 
    def stats(self, symbol: str | None = None) -> dict:
        closed = self.closed(symbol)
        total = len(closed)
        wins = sum(1 for t in closed if t.status == "WIN")
        losses = sum(1 for t in closed if t.status == "LOSS")
        gross_profit = sum(t.profit for t in closed if t.profit > 0)
        gross_loss = -sum(t.profit for t in closed if t.profit < 0)
        net = sum(t.profit for t in closed)
        win_rate = round(wins / total * 100, 2) if total else 0.0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_profit": round(net, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": profit_factor,
        }
 
    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> TradeRecord:
        context = {}
        if row["context"]:
            try:
                context = json.loads(row["context"])
            except json.JSONDecodeError:
                context = {}
        return TradeRecord(
            id=row["id"],
            symbol=row["symbol"],
            direction=row["direction"],
            confidence=row["confidence"],
            entry_price=row["entry_price"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            volume=row["volume"],
            reason=row["reason"] or "",
            context=context,
            ticket=row["ticket"],
            status=row["status"],
            exit_price=row["exit_price"],
            profit=row["profit"],
            opened_at=row["opened_at"] or "",
            closed_at=row["closed_at"] or "",
        )