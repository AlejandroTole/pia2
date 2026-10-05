"""Regresión: order_check usa retcode 0 para éxito.

TRADE_RETCODE_DONE (10009) aplica solo a order_send. Comparar el pre-chequeo
contra 10009 rechazaba las órdenes aunque el chequeo pasara.
"""

from types import SimpleNamespace

import pia2.brokers.mt5_broker as mt5_broker_mod
from pia2.brokers.mt5_broker import MT5Broker


class FakeMT5:
    TRADE_RETCODE_DONE = 10009
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_FOK = 2
    ORDER_FILLING_RETURN = 3

    def __init__(self, check_retcode=0):
        self.check_retcode = check_retcode
        self.sent = []

    def symbol_info(self, symbol):
        return SimpleNamespace(filling_mode=None)

    def order_check(self, request):
        return SimpleNamespace(retcode=self.check_retcode, comment="")

    def order_send(self, request):
        self.sent.append(request)
        return SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE,
            order=777,
            price=1.1000,
        )

    def last_error(self):
        return ("fake error", 0)


def _broker(monkeypatch, check_retcode=0):
    fake = FakeMT5(check_retcode=check_retcode)
    broker = MT5Broker()
    monkeypatch.setattr(broker, "_ensure_lib", lambda: fake)
    monkeypatch.setattr(
        broker,
        "symbol_spec",
        lambda symbol: SimpleNamespace(point=0.00001, trade_stops_level=0),
    )
    monkeypatch.setattr(
        broker,
        "get_tick",
        lambda symbol: SimpleNamespace(bid=1.10000, ask=1.10001),
    )
    monkeypatch.setattr(mt5_broker_mod, "normalize_volume", lambda spec, volume: volume)
    monkeypatch.setattr(
        mt5_broker_mod,
        "round_price",
        lambda spec, price: round(price, 5),
    )
    return broker, fake


def test_order_check_zero_means_success(monkeypatch):
    broker, fake = _broker(monkeypatch, check_retcode=0)

    result = broker.place_order(
        symbol="EURUSD.PRO",
        direction="BUY",
        volume=0.11,
        stop_loss=1.0980,
        take_profit=1.1020,
        magic=999999,
        comment="t",
    )

    assert result.ok is True
    assert result.ticket == 777
    assert len(fake.sent) == 1


def test_order_check_nonzero_still_rejects(monkeypatch):
    broker, fake = _broker(monkeypatch, check_retcode=10016)

    result = broker.place_order(
        symbol="EURUSD.PRO",
        direction="BUY",
        volume=0.11,
        stop_loss=1.0980,
        take_profit=1.1020,
        magic=999999,
        comment="t",
    )

    assert result.ok is False
    assert len(fake.sent) == 0
