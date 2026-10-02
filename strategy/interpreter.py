"""Interpretación cualitativa del mercado (tendencia/momentum/volatilidad).
 
La volatilidad se mide de forma relativa al precio (ATR/precio), no con un
umbral absoluto como en la v1 (0.0005), que no sirve igual para EURUSD que
para XAUUSD.
"""
 
from __future__ import annotations
 
from typing import Any

from config.schema import IndicatorsConfig
from pia2.market.instruments import SymbolSpec
from pia2.strategy.trade_setup import TradeSetup, build_trade_setup


def interpret_market(price: float, ema_fast: float, ema_slow: float, rsi: float,
                     atr: float) -> dict:
    trend = "Alcista" if ema_fast > ema_slow else "Bajista"
 
    if rsi > 70:
        momentum = "Sobrecompra"
    elif rsi < 30:
        momentum = "Sobreventa"
    elif rsi > 50:
        momentum = "Positivo"
    else:
        momentum = "Débil"
 
    atr_ratio = (atr / price) if price else 0.0
    volatility = "Alta" if atr_ratio > 0.0015 else "Moderada"
 
    return {
        "trend": trend,
        "momentum": momentum,
        "volatility": volatility,
        "atr_ratio": round(atr_ratio, 6),
    }


def reference_trade_signal(
    price: float,
    ema_fast: float,
    ema_slow: float,
    rsi: float,
    atr: float,
    candle_context: dict | None = None,
) -> str:
    """Regla determinista de referencia para comparar con la señal del LLM.

    Tiene prioridad la tendencia EMA, confirma con RSI y, si hay un patrón
    de velas fuerte, incorpora esa señal como último filtro. Tiene el mismo
    SL/TP que la regla de trading real: ATR * multiplicadores de setup.
    """
    trend = "BUY" if ema_fast > ema_slow else "SELL"
    candle_bias = str((candle_context or {}).get("bias", "NEUTRAL")).upper()
    candle_strength = float((candle_context or {}).get("strength", 0) or 0)

    if candle_bias in {"BUY", "SELL"} and candle_strength >= 60:
        if candle_bias == "BUY" and rsi >= 50:
            return "BUY"
        if candle_bias == "SELL" and rsi <= 50:
            return "SELL"

    if trend == "BUY" and rsi >= 55:
        return "BUY"
    if trend == "SELL" and rsi <= 45:
        return "SELL"

    if price <= 0 or atr <= 0:
        return "WAIT"
    return "WAIT"


def build_reference_setup(
    price: float,
    atr: float,
    signal: str,
    cfg: IndicatorsConfig,
    spec: SymbolSpec | None = None,
) -> TradeSetup:
    if spec is None:
        spec = SymbolSpec(
            name="REFERENCE",
            digits=5,
            point=0.00001,
            tick_size=0.00001,
            tick_value=1.0,
            contract_size=100000,
        )
    return build_trade_setup(spec, signal, price, atr, cfg)