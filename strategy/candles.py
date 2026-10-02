"""Análisis básico de velas japonesas para sesgo operativo.

El objetivo no es predecir por sí solo, sino aportar contexto adicional
al analista (LLM) con patrones recientes y una señal de sesgo.
"""

from __future__ import annotations

import math

import pandas as pd


def _to_float(value) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(out):
        return 0.0
    return out


def _candle_parts(row: pd.Series) -> tuple[float, float, float, float]:
    open_ = _to_float(row.get("open"))
    high = _to_float(row.get("high"))
    low = _to_float(row.get("low"))
    close = _to_float(row.get("close"))

    body = abs(close - open_)
    full_range = max(high - low, 1e-12)
    upper_wick = max(0.0, high - max(open_, close))
    lower_wick = max(0.0, min(open_, close) - low)
    return body, full_range, upper_wick, lower_wick


def analyze_candles(df: pd.DataFrame) -> dict:
    """Detecta patrones simples de velas y devuelve sesgo cualitativo.

    Return:
    {
      "pattern": str,
      "bias": "BUY" | "SELL" | "NEUTRAL",
      "strength": int,   # 0..100
      "summary": str
    }
    """
    neutral = {
        "pattern": "NONE",
        "bias": "NEUTRAL",
        "strength": 0,
        "summary": "Sin patrón de velas claro.",
    }

    if df is None or df.empty:
        return neutral

    if not {"open", "high", "low", "close"}.issubset(df.columns):
        return neutral

    last = df.iloc[-1]
    body, full_range, upper_wick, lower_wick = _candle_parts(last)
    body_ratio = body / full_range

    # Patrones de 2 velas (engulfing) tienen prioridad por robustez.
    if len(df) >= 2:
        prev = df.iloc[-2]
        prev_open = _to_float(prev.get("open"))
        prev_close = _to_float(prev.get("close"))
        last_open = _to_float(last.get("open"))
        last_close = _to_float(last.get("close"))

        prev_bear = prev_close < prev_open
        prev_bull = prev_close > prev_open
        last_bull = last_close > last_open
        last_bear = last_close < last_open

        bullish_engulfing = (
            prev_bear
            and last_bull
            and last_open <= prev_close
            and last_close >= prev_open
        )
        if bullish_engulfing:
            return {
                "pattern": "BULLISH_ENGULFING",
                "bias": "BUY",
                "strength": 75,
                "summary": "Engulfing alcista en la vela más reciente.",
            }

        bearish_engulfing = (
            prev_bull
            and last_bear
            and last_open >= prev_close
            and last_close <= prev_open
        )
        if bearish_engulfing:
            return {
                "pattern": "BEARISH_ENGULFING",
                "bias": "SELL",
                "strength": 75,
                "summary": "Engulfing bajista en la vela más reciente.",
            }

    # Patrones de 1 vela.
    if body_ratio <= 0.2 and upper_wick >= body * 2 and lower_wick >= body * 2:
        return {
            "pattern": "DOJI",
            "bias": "NEUTRAL",
            "strength": 40,
            "summary": "Doji: indecisión del mercado.",
        }

    if lower_wick >= body * 2 and upper_wick <= max(body * 0.6, 1e-12):
        return {
            "pattern": "HAMMER",
            "bias": "BUY",
            "strength": 60,
            "summary": "Hammer: posible rechazo bajista y giro alcista.",
        }

    if upper_wick >= body * 2 and lower_wick <= max(body * 0.6, 1e-12):
        return {
            "pattern": "SHOOTING_STAR",
            "bias": "SELL",
            "strength": 60,
            "summary": "Shooting Star: posible rechazo alcista y giro bajista.",
        }

    # Microestructura de 3 velas si no hubo patrón claro.
    if len(df) >= 3:
        c1 = _to_float(df.iloc[-3].get("close"))
        c2 = _to_float(df.iloc[-2].get("close"))
        c3 = _to_float(df.iloc[-1].get("close"))

        if c1 < c2 < c3:
            return {
                "pattern": "THREE_RISING_CLOSES",
                "bias": "BUY",
                "strength": 45,
                "summary": "Tres cierres ascendentes consecutivos.",
            }
        if c1 > c2 > c3:
            return {
                "pattern": "THREE_FALLING_CLOSES",
                "bias": "SELL",
                "strength": 45,
                "summary": "Tres cierres descendentes consecutivos.",
            }

    return neutral
