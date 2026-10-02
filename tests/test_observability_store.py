from datetime import datetime, timezone

from pia2.observability.store import ObservabilityStore


def test_signal_store_records_signal_and_block_reason(tmp_path):
    store = ObservabilityStore(str(tmp_path / "observability.db"))
    now = datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)

    store.record_signal(
        symbol="EURUSD.PRO",
        timestamp=now,
        features={"trend": "Alcista", "rsi": 62, "atr": 0.0008},
        raw_llm_response='{"signal":"BUY","confidence":72}',
        decision="BUY",
        block_filter="news",
        latency_ms=250,
    )

    rows = store.recent_signals("EURUSD.PRO", limit=10)
    assert len(rows) == 1
    assert rows[0]["decision"] == "BUY"
    assert rows[0]["block_filter"] == "news"
    assert rows[0]["latency_ms"] == 250
    assert rows[0]["raw_llm_response"] == '{"signal":"BUY","confidence":72}'

    store.close()


def test_account_snapshot_store_records_balance_and_equity(tmp_path):
    store = ObservabilityStore(str(tmp_path / "observability.db"))
    now = datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)

    store.record_account_snapshot(
        timestamp=now,
        symbol="EURUSD.PRO",
        balance=10000.0,
        equity=9800.0,
        margin_free=1500.0,
        margin_level=220.0,
        open_positions=1,
    )

    rows = store.recent_account_snapshots("EURUSD.PRO", limit=10)
    assert len(rows) == 1
    assert rows[0]["balance"] == 10000.0
    assert rows[0]["equity"] == 9800.0
    assert rows[0]["open_positions"] == 1

    store.close()
