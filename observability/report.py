"""Helpers para resumir la observabilidad guardada en SQLite."""

from __future__ import annotations

from pathlib import Path

from pia2.observability.store import ObservabilityStore


def summarize(db_path: str = "data/runtime/observability.db") -> dict:
    """Devuelve un resumen con señales, órdenes y snapshots recientes."""
    store = ObservabilityStore(db_path)
    try:
        signals = store.recent_signals(limit=10)
        orders = store.recent_orders(limit=10)
        snapshots = store.recent_account_snapshots(limit=10)
        return {
            "signals": signals,
            "orders": orders,
            "snapshots": snapshots,
            "count_signals": len(signals),
            "count_orders": len(orders),
            "count_snapshots": len(snapshots),
            "db_exists": Path(db_path).exists(),
        }
    finally:
        store.close()
