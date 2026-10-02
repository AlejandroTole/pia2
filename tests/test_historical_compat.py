import importlib


def test_legacy_agents_historical_module_imports():
    module = importlib.import_module("agents.historical_agent.multi_historical_builder")
    assert hasattr(module, "MultiHistoricalBuilder")


def test_settings_module_imports_without_mt5_runtime():
    settings = importlib.import_module("config.settings")
    assert hasattr(settings, "MIN_FUTURE_MOVE_ATR_RATIO")
    assert isinstance(settings.MIN_FUTURE_MOVE_ATR_RATIO, float)
