from types import SimpleNamespace

from config.loader import load_config
from pia2.brokers.mt5_broker import MT5Broker
from pia2.core.orchestrator import Orchestrator


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2

    def __init__(self, trade_mode=0, account_allowed=True, terminal_allowed=True):
        self._account = SimpleNamespace(
            trade_mode=trade_mode,
            trade_allowed=account_allowed,
            login=123,
        )
        self._terminal = SimpleNamespace(trade_allowed=terminal_allowed)
        self.shutdown_called = False

    def initialize(self, **kwargs):
        return True

    def account_info(self):
        return self._account

    def terminal_info(self):
        return self._terminal

    def shutdown(self):
        self.shutdown_called = True


def test_config_supports_safe_execution_axes(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "execution: simulated\naccount_type_required: demo\nmode: demo\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.execution == "simulated"
    assert config.account_type_required == "demo"
    assert config.is_real is False


def test_mt5_rejects_live_account_when_demo_is_required():
    broker = MT5Broker(account_type_required="demo")
    broker._mt5 = FakeMT5(trade_mode=FakeMT5.ACCOUNT_TRADE_MODE_REAL)

    assert broker.connect() is False
    assert broker._mt5.shutdown_called is True


def test_mt5_rejects_when_trading_is_disabled():
    broker = MT5Broker(account_type_required="demo")
    broker._mt5 = FakeMT5(account_allowed=False)

    assert broker.connect() is False
    assert broker._mt5.shutdown_called is True


def test_stop_file_activates_kill_switch(tmp_path):
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator._stop_file = tmp_path / "STOP"

    assert orchestrator._kill_switch_active() is False
    orchestrator._stop_file.touch()
    assert orchestrator._kill_switch_active() is True