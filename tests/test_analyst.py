"""Tests del analista LLM (ai/analyst.py): parseo robusto de la respuesta.

El analista pide JSON al modelo pero debe degradar a WAIT ante cualquier
salida mal formada, sin romper el ciclo.
"""

from pia2.ai.analyst import Analysis, MarketSnapshot, TradingAnalyst


class FakeClient:
    """Cliente LLM falso: devuelve una respuesta prefijada (o lanza)."""

    def __init__(self, response: str = "", error: Exception | None = None):
        self.response = response
        self.error = error

    def generate(self, prompt: str) -> str:
        if self.error is not None:
            raise self.error
        return self.response


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="EURUSD", price=1.1000, trend="Alcista",
        momentum="Alcista", volatility="Media", rsi=55.0, atr=0.0020,
    )


def _analyze(raw: str, **kwargs) -> Analysis:
    return TradingAnalyst(FakeClient(raw, **kwargs)).analyze(_snapshot())


def test_valid_json_signal():
    a = _analyze('{"signal":"BUY","confidence":80,"reason":"tendencia"}')
    assert (a.signal, a.confidence) == ("BUY", 80)


def test_json_with_surrounding_text():
    a = _analyze('Claro, aquí va:\n{"signal":"SELL","confidence":65,"reason":"divergencia"}\nFin.')
    assert (a.signal, a.confidence) == ("SELL", 65)


def test_garbage_degrades_to_wait():
    a = _analyze("no sé, el mercado está raro hoy")
    assert a.signal == "WAIT"
    assert a.confidence == 0.0


def test_invalid_signal_degrades_to_wait():
    a = _analyze('{"signal":"MOON","confidence":99,"reason":"x"}')
    assert a.signal == "WAIT"


def test_client_error_degrades_to_wait():
    a = _analyze("", error=TimeoutError("ollama lento"))
    assert a.signal == "WAIT"
    assert "LLM error" in a.reason


def test_confidence_is_clamped():
    a = _analyze('{"signal":"BUY","confidence":150,"reason":"x"}')
    assert a.confidence <= 100
    a = _analyze('{"signal":"BUY","confidence":-20,"reason":"x"}')
    assert a.confidence >= 0
