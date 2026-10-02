
"""Analista de trading basado en LLM, con salida estructurada (JSON).
 
La v1 parseaba texto libre del modelo con regex (frágil). Aquí se le pide al
LLM que responda en JSON y se parsea de forma robusta, con validación y
fallback si el modelo devuelve algo mal formado.
"""
 
from __future__ import annotations
 
import json
import re
from dataclasses import dataclass, field
 
from pia2.ai.llm_client import LLMClient
from pia2.memory.store import TradeStore
 
_VALID_SIGNALS = ("BUY", "SELL", "WAIT")
 
 
@dataclass
class Analysis:
    signal: str = "WAIT"
    confidence: float = 0.0
    reason: str = ""
    raw: str = ""
 
    def as_dict(self) -> dict:
        return {"signal": self.signal, "confidence": self.confidence, "reason": self.reason}
 
 
@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    trend: str
    momentum: str
    volatility: str
    rsi: float
    atr: float
    extra: dict = field(default_factory=dict)
 
 
class TradingAnalyst:
    def __init__(self, client: LLMClient):
        self.client = client
 
    def analyze(self, snapshot: MarketSnapshot, memory_context: dict | None = None) -> Analysis:
        prompt = self._build_prompt(snapshot, memory_context or {})
        try:
            raw = self.client.generate(prompt)
        except Exception as exc:
            return Analysis(
                signal="WAIT",
                confidence=0.0,
                reason=f"LLM error: {exc}",
                raw="",
            )

        analysis = self._parse(raw)
        
        # Aplicar confianza adaptativa basada en histórico del símbolo
        if memory_context:
            analysis.confidence = self._apply_adaptive_confidence(
                analysis.confidence,
                memory_context
            )
        
        return analysis
    
    def _apply_adaptive_confidence(self, base_confidence: float, memory: dict) -> float:
        """Ajusta la confianza basada en win_rate histórico del símbolo.
        
        - Si win_rate es bajo (<50%), reduce confianza (más conservador)
        - Si win_rate es alto (>65%), permite mayor confianza
        - Si no hay historial suficiente, mantén base_confidence
        """
        total_trades = memory.get('total_trades', 0)
        win_rate = memory.get('win_rate', 50)
        
        # Necesitamos al menos 5 operaciones para confiar en el histórico
        if total_trades < 5:
            return base_confidence
        
        # Factor de ajuste basado en win_rate
        if win_rate < 45:
            # Win rate muy bajo: reducir confianza 20%
            adjusted = base_confidence * 0.8
        elif win_rate < 50:
            # Win rate bajo: reducir confianza 10%
            adjusted = base_confidence * 0.9
        elif win_rate > 65:
            # Win rate alto: permitir mayor confianza (+5%)
            adjusted = min(100, base_confidence * 1.05)
        else:
            # Win rate normal (50-65%): mantener base_confidence
            adjusted = base_confidence
        
        return max(0, min(100, adjusted))
    
    def _build_prompt(self, s: MarketSnapshot, memory: dict) -> str:
        # Construir contexto de memoria con estadísticas reales
        total_trades = memory.get('total_trades', 0)
        win_rate = memory.get('win_rate', 0)
        net_profit = memory.get('net_profit', 0)
        profit_factor = memory.get('profit_factor', 0) or 1.0
        candles = (s.extra or {}).get("candles", {})
        candle_pattern = candles.get("pattern", "NONE")
        candle_bias = candles.get("bias", "NEUTRAL")
        candle_strength = candles.get("strength", 0)
        candle_summary = candles.get("summary", "")
        news = (s.extra or {}).get("news", {})
        news_bias = news.get("bias", "NEUTRAL")
        news_confidence = news.get("confidence", 0)
        news_summary = news.get("summary", "")
        
        # Contexto histórico
        historical_context = memory.get('historical_patterns', '')
        
        return f"""Eres un analista profesional de Day Trading especializado en Forex y Metales.

    Tu objetivo NO es generar muchas operaciones, sino identificar únicamente aquellas que tengan una ventaja estadística clara (edge).

    La preservación del capital es la prioridad absoluta.

    Si existe cualquier duda razonable o señales contradictorias, responde WAIT.

    Nunca operes por FOMO (Fear Of Missing Out).

    --------------------------------------------------
    DATOS DEL MERCADO
    --------------------------------------------------

    Símbolo: {s.symbol}

    Precio actual: {s.price}

    Tendencia: {s.trend}

    Momentum: {s.momentum}

    Volatilidad: {s.volatility}

    RSI: {s.rsi}

    ATR: {s.atr}

    --------------------------------------------------
    LECTURA DE VELAS
    --------------------------------------------------

    Patrón detectado:
    {candle_pattern}

    Sesgo:
    {candle_bias}

    Fuerza:
    {candle_strength}/100

    Resumen:
    {candle_summary}

    --------------------------------------------------
    ANÁLISIS DE NOTICIAS
    --------------------------------------------------

    Sesgo:
    {news_bias}

    Confianza:
    {news_confidence}/100

    Resumen:
    {news_summary}

    --------------------------------------------------
    MEMORIA HISTÓRICA
    --------------------------------------------------

    Operaciones anteriores sobre {s.symbol}

    Total operaciones:
    {total_trades}

    Win Rate:
    {win_rate}%

    Ganancia neta:
    ${net_profit:.2f}

    Profit Factor:
    {profit_factor}

    Casos similares:
    {historical_context}

    --------------------------------------------------
    REGLAS DE DECISIÓN
    --------------------------------------------------

    Analiza SIEMPRE en este orden:

    1. Tendencia general del mercado.

    2. Acción del precio y estructura.

    3. Patrón de velas.

    4. Momentum.

    5. RSI.

    6. Volatilidad (ATR).

    7. Noticias.

    8. Memoria histórica.

    La memoria histórica SOLO debe utilizarse para ajustar la confianza de la decisión.

    Nunca copies operaciones anteriores.

    El mercado actual siempre tiene prioridad sobre la memoria.

    --------------------------------------------------
    EXISTE VENTAJA ESTADÍSTICA SOLAMENTE SI
    --------------------------------------------------

    La mayoría de estos factores están alineados:

    ✓ Tendencia clara

    ✓ Patrón de velas consistente

    ✓ Momentum confirma

    ✓ RSI confirma

    ✓ Volatilidad suficiente

    ✓ Noticias no contradicen

    ✓ Historial no muestra un rendimiento claramente negativo

    Si varios factores importantes se contradicen, responde WAIT.

    --------------------------------------------------
    RESPONDE WAIT SI
    --------------------------------------------------

    - Tendencia y velas apuntan en direcciones distintas.

    - Momentum contradice la tendencia.

    - RSI contradice el movimiento esperado.

    - Las noticias generan incertidumbre.

    - La volatilidad es demasiado baja.

    - La estructura del mercado es confusa.

    - No existe suficiente evidencia para justificar una entrada.

    - La confianza final sería menor de 65.

    --------------------------------------------------
    AJUSTE POR MEMORIA
    --------------------------------------------------

    Si el Win Rate histórico del símbolo es inferior al 50%, sé más conservador.

    Reduce la confianza cuando existan antecedentes negativos similares.

    Nunca abras una operación únicamente porque antes funcionó.

    --------------------------------------------------
    ESCALA DE CONFIANZA
    --------------------------------------------------

    95-100 = Confluencia excepcional (muy raro)

    90-94 = Configuración excelente

    80-89 = Alta probabilidad

    70-79 = Buena ventaja estadística

    65-69 = Ventaja limitada

    Menor de 65 = WAIT

    Nunca devuelvas una confianza superior a 95 salvo que TODOS los factores estén claramente alineados.

    --------------------------------------------------
    REGLAS IMPORTANTES
    --------------------------------------------------

    No inventes información.

    No asumas datos que no fueron proporcionados.

    Si falta información importante, responde WAIT.

    Es mejor perder una oportunidad que tomar una operación de baja calidad.

    --------------------------------------------------
    FORMATO DE RESPUESTA
    --------------------------------------------------

    Responde EXCLUSIVAMENTE con un objeto JSON válido.

    No agregues explicaciones.

    No uses Markdown.

    No escribas texto antes o después del JSON.

    Formato:

    {{
        "signal": "BUY|SELL|WAIT",
        "confidence": 0,
        "reason": "Máximo 25 palabras explicando los factores principales que motivaron la decisión."
    }}
    """
 
    def _parse(self, raw: str) -> Analysis:
        data = self._extract_json(raw)
        if data is None:
            return Analysis(
                signal="WAIT",
                confidence=0.0,
                reason="Respuesta del LLM no es JSON válido",
                raw=raw,
            )
 
        signal = str(data.get("signal", "WAIT")).upper().strip()
        if signal not in _VALID_SIGNALS:
            signal = "WAIT"
 
        confidence = self._coerce_confidence(data.get("confidence", 0))
        reason = str(data.get("reason", "")).strip()
 
        return Analysis(signal=signal, confidence=confidence, reason=reason, raw=raw)
 
    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Buscar el primer bloque {...} en el texto.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None
 
    @staticmethod
    def _coerce_confidence(value) -> float:
        try:
            conf = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(100.0, conf))