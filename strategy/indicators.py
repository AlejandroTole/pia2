"""Indicadores técnicos (EMA, RSI, ATR) sobre un DataFrame de velas."""
 
from __future__ import annotations
 
import pandas as pd
import ta
 
from config.schema import IndicatorsConfig
 
 
def add_indicators(df: pd.DataFrame, cfg: IndicatorsConfig) -> pd.DataFrame:
    df = df.copy()
    df["EMA_FAST"] = ta.trend.ema_indicator(df["close"], window=cfg.ema_fast)
    df["EMA_SLOW"] = ta.trend.ema_indicator(df["close"], window=cfg.ema_slow)
    df["RSI"] = ta.momentum.rsi(df["close"], window=cfg.rsi_period)
    df["ATR"] = ta.volatility.average_true_range(
        high=df["high"], low=df["low"], close=df["close"], window=cfg.atr_period
    )
    return df