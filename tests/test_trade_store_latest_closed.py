from pia2.memory.store import TradeRecord, TradeStore


def test_latest_closed_filters_direction_and_status(tmp_path):
    db = tmp_path / "pia.db"
    store = TradeStore(str(db))

    store.save_decision(
        TradeRecord(
            symbol="XAUUSD.PRO",
            direction="BUY",
            confidence=80,
            entry_price=100,
            stop_loss=99,
            take_profit=102,
            volume=0.01,
            ticket=101,
            opened_at="2026-07-23T08:00:00",
        )
    )
    store.update_result_by_ticket(
        101,
        "LOSS",
        exit_price=99,
        profit=-1,
        closed_at="2026-07-23T08:10:00",
    )

    store.save_decision(
        TradeRecord(
            symbol="XAUUSD.PRO",
            direction="SELL",
            confidence=70,
            entry_price=100,
            stop_loss=101,
            take_profit=98,
            volume=0.01,
            ticket=102,
            opened_at="2026-07-23T09:00:00",
        )
    )
    store.update_result_by_ticket(
        102,
        "WIN",
        exit_price=98,
        profit=2,
        closed_at="2026-07-23T09:10:00",
    )

    latest_buy = store.latest_closed("XAUUSD.PRO", "BUY")
    latest_sell = store.latest_closed("XAUUSD.PRO", "SELL")

    assert latest_buy is not None
    assert latest_buy.direction == "BUY"
    assert latest_buy.status == "LOSS"
    assert latest_buy.closed_at == "2026-07-23T08:10:00"

    assert latest_sell is not None
    assert latest_sell.direction == "SELL"
    assert latest_sell.status == "WIN"
    assert latest_sell.closed_at == "2026-07-23T09:10:00"

    store.close()
