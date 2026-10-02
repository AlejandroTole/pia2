import textwrap
 
import pytest
 
from config.loader import ConfigError, load_config
 
 
def write_config(tmp_path, content: str):
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path
 
 
def test_load_valid_config(tmp_path):
    path = write_config(tmp_path, """
        mode: demo
        symbols: [EURUSD, XAUUSD]
        symbol_suffix: ".PRO"
        timeframe: M15
        risk:
          risk_per_trade_pct: 1.0
          max_daily_loss_pct: 2.0
        schedule:
          timezone: America/Toronto
          sessions:
            - start: "08:00"
              end: "11:00"
          trade_days: [Mon, Tue]
    """)
    config = load_config(path)
    assert config.mode == "demo"
    assert config.symbols == ["EURUSD", "XAUUSD"]
    assert config.broker_symbols() == ["EURUSD.PRO", "XAUUSD.PRO"]
    assert config.risk.risk_per_trade_pct == 1.0
    assert config.is_real is False
 
 
def test_real_mode_flag(tmp_path):
    path = write_config(tmp_path, """
        mode: real
        symbols: [EURUSD]
    """)
    config = load_config(path)
    assert config.is_real is True
 
 
def test_invalid_mode_raises(tmp_path):
    path = write_config(tmp_path, """
        mode: paper
        symbols: [EURUSD]
    """)
    with pytest.raises(ConfigError):
        load_config(path)
 
 
def test_empty_symbols_raises(tmp_path):
    path = write_config(tmp_path, """
        mode: demo
        symbols: []
    """)
    with pytest.raises(ConfigError):
        load_config(path)
 
 
def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")
 
 
def test_invalid_timeframe_raises(tmp_path):
    path = write_config(tmp_path, """
        mode: demo
        symbols: [EURUSD]
        timeframe: M7
    """)
    with pytest.raises(ConfigError):
        load_config(path)


def test_candle_policy_loaded(tmp_path):
    path = write_config(tmp_path, """
        mode: demo
        symbols: [EURUSD]
        candle_policy:
          enabled: true
          min_strength: 55
          conflict_penalty: 20
          aligned_boost: 10
          veto_strength: 85
    """)
    config = load_config(path)
    assert config.candle_policy.enabled is True
    assert config.candle_policy.min_strength == 55
    assert config.candle_policy.conflict_penalty == 20
    assert config.candle_policy.aligned_boost == 10
    assert config.candle_policy.veto_strength == 85


def test_news_config_loaded(tmp_path):
        path = write_config(tmp_path, """
                mode: demo
                symbols: [EURUSD]
                news:
                    enabled: true
                    refresh_minutes: 15
                    reaction_windows_minutes: [15, 60, 240]
                    min_pattern_events: 30
                    block_high_before_minutes: 20
                    block_high_after_minutes: 45
        """)
        config = load_config(path)
        assert config.news.enabled is True
        assert config.news.refresh_minutes == 15
        assert config.news.reaction_windows_minutes == [15, 60, 240]
        assert config.news.min_pattern_events == 30


def test_observability_loaded(tmp_path):
        path = write_config(tmp_path, """
                mode: demo
                symbols: [EURUSD]
                observability:
                    log_level: DEBUG
                    heartbeat_seconds: 15
                    show_symbol_summary: true
        """)
        config = load_config(path)
        assert config.observability.log_level == "DEBUG"
        assert config.observability.heartbeat_seconds == 15
        assert config.observability.show_symbol_summary is True


def test_risk_new_controls_loaded(tmp_path):
    path = write_config(tmp_path, """
        mode: demo
        symbols: [EURUSD]
        risk:
          block_symbol_stacking: true
          cooldown_minutes_after_loss: 45
    """)
    config = load_config(path)
    assert config.risk.block_symbol_stacking is True
    assert config.risk.cooldown_minutes_after_loss == 45


def test_unknown_config_keys_warn(tmp_path):
    path = write_config(tmp_path, """
        mode: demo
        symbols: [EURUSD]
        not_a_real_key: true
    """)
    with pytest.warns(UserWarning, match="not_a_real_key"):
        load_config(path)