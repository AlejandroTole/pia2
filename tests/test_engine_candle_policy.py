from types import SimpleNamespace

from pia2.ai.analyst import Analysis
from pia2.core.engine import TradingEngine


def _engine_with_policy(enabled=True, min_strength=50, penalty=15, boost=8, veto=80):
    return SimpleNamespace(
        config=SimpleNamespace(
            candle_policy=SimpleNamespace(
                enabled=enabled,
                min_strength=min_strength,
                conflict_penalty=penalty,
                aligned_boost=boost,
                veto_strength=veto,
            )
        )
    )


def test_candle_policy_boosts_aligned_signal():
    dummy_engine = _engine_with_policy()
    analysis = Analysis(signal="BUY", confidence=70, reason="base")
    candle = {"pattern": "BULLISH_ENGULFING", "bias": "BUY", "strength": 75}

    updated = TradingEngine._apply_candle_policy(dummy_engine, analysis, candle)

    assert updated.signal == "BUY"
    assert updated.confidence == 78
    assert "confirman BUY" in updated.reason


def test_candle_policy_penalizes_conflict():
    dummy_engine = _engine_with_policy()
    analysis = Analysis(signal="BUY", confidence=70, reason="base")
    candle = {"pattern": "SHOOTING_STAR", "bias": "SELL", "strength": 60}

    updated = TradingEngine._apply_candle_policy(dummy_engine, analysis, candle)

    assert updated.signal == "BUY"
    assert updated.confidence == 55
    assert "contradicen" in updated.reason


def test_candle_policy_vetoes_strong_conflict():
    dummy_engine = _engine_with_policy(veto=75)
    analysis = Analysis(signal="BUY", confidence=82, reason="base")
    candle = {"pattern": "BEARISH_ENGULFING", "bias": "SELL", "strength": 90}

    updated = TradingEngine._apply_candle_policy(dummy_engine, analysis, candle)

    assert updated.signal == "WAIT"
    assert updated.confidence == 0
    assert "Veto" in updated.reason
