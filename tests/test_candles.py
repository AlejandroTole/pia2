import pandas as pd

from pia2.strategy.candles import analyze_candles


def test_detects_bullish_engulfing():
    df = pd.DataFrame(
        [
            {"open": 1.1010, "high": 1.1015, "low": 1.0990, "close": 1.0995},
            {"open": 1.0993, "high": 1.1025, "low": 1.0990, "close": 1.1020},
        ]
    )

    result = analyze_candles(df)
    assert result["pattern"] == "BULLISH_ENGULFING"
    assert result["bias"] == "BUY"


def test_detects_shooting_star():
    df = pd.DataFrame(
        [
            {"open": 1.1000, "high": 1.1008, "low": 1.0996, "close": 1.1004},
            {"open": 1.1006, "high": 1.1040, "low": 1.1005, "close": 1.1008},
        ]
    )

    result = analyze_candles(df)
    assert result["pattern"] == "SHOOTING_STAR"
    assert result["bias"] == "SELL"


def test_detects_three_rising_closes():
    df = pd.DataFrame(
        [
            {"open": 1.1000, "high": 1.1008, "low": 1.0998, "close": 1.1002},
            {"open": 1.1002, "high": 1.1011, "low": 1.1001, "close": 1.1007},
            {"open": 1.1007, "high": 1.1015, "low": 1.1006, "close": 1.1012},
        ]
    )

    result = analyze_candles(df)
    assert result["pattern"] == "THREE_RISING_CLOSES"
    assert result["bias"] == "BUY"
