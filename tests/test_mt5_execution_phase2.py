from types import SimpleNamespace

from pia2.brokers.mt5_broker import MT5Broker


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 0
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    SYMBOL_FILLING_FOK = 1
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.selected_symbols = []
        self.sent_requests = []
        self.order_checks = []
        self._account = SimpleNamespace(
            balance=10000.0,
            equity=10000.0,
            currency="USD",
            leverage=100,
            login=12345,
            margin_free=500.0,
            margin_level=200.0,
            trade_mode=self.ACCOUNT_TRADE_MODE_DEMO,
            trade_allowed=True,
        )
        self._terminal = SimpleNamespace(trade_allowed=True)
        self._symbols = {
            "EURUSD.PRO": SimpleNamespace(
                digits=5,
                point=0.00001,
                trade_tick_size=0.00001,
                trade_tick_value=1.0,
                trade_contract_size=100000,
                volume_min=0.01,
                volume_max=10.0,
                volume_step=0.01,
                trade_stops_level=30,
                trade_freeze_level=10,
                filling_mode=self.SYMBOL_FILLING_FOK,
                trade_mode=self.ACCOUNT_TRADE_MODE_DEMO,
            )
        }

    def initialize(self, **kwargs):
        return True

    def account_info(self):
        return self._account

    def terminal_info(self):
        return self._terminal

    def shutdown(self):
        return None

    def symbol_select(self, symbol, select):
        self.selected_symbols.append((symbol, select))
        return True

    def symbol_info(self, symbol):
        return self._symbols.get(symbol)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=1.10000, ask=1.10010, time=1700000000)

    def order_check(self, request):
        self.order_checks.append(request)
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, comment="OK")

    def order_send(self, request):
        self.sent_requests.append(request)
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=42, price=request["price"], comment="OK")


def test_mt5_connect_selects_symbols_and_validates_symbol_metadata(monkeypatch):
    broker = MT5Broker(account_type_required="demo", symbols=["EURUSD.PRO"])
    mt5 = FakeMT5()
    broker._mt5 = mt5

    assert broker.connect() is True
    assert broker._mt5.selected_symbols == [("EURUSD.PRO", True)]


def test_mt5_place_order_uses_symbol_filling_mode_and_configured_deviation():
    broker = MT5Broker(
        account_type_required="demo",
        symbols=["EURUSD.PRO"],
        default_deviation=12,
    )
    mt5 = FakeMT5()
    broker._mt5 = mt5

    result = broker.place_order(
        symbol="EURUSD.PRO",
        direction="BUY",
        volume=0.10,
        stop_loss=1.09900,
        take_profit=1.10200,
        magic=123,
        comment="phase2",
    )

    assert result.ok is True
    assert mt5.sent_requests[0]["deviation"] == 12
    assert mt5.sent_requests[0]["type_filling"] == FakeMT5.ORDER_FILLING_FOK
    assert len(mt5.order_checks) == 1
