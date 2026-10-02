"""Plan de operación: entrada, Stop Loss y Take Profit basados en ATR.
 
Único lugar que calcula la distancia de SL/TP. RiskManager reutiliza ese
sl_distance para dimensionar el lote (evita desincronización). El redondeo se
hace a los dígitos reales del símbolo, no fijo a 5 como la v1.
"""
 
from __future__ import annotations
 
from dataclasses import dataclass
 
from config.schema import IndicatorsConfig
from pia2.market.instruments import SymbolSpec, round_price
 
 
@dataclass
class TradeSetup:
    valid: bool
    signal: str = "WAIT"
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    sl_distance: float = 0.0
    tp_distance: float = 0.0
    risk_reward: float = 0.0
    reason: str = ""
 
 
def build_trade_setup(spec: SymbolSpec, signal: str, price: float, atr: float,
                      cfg: IndicatorsConfig) -> TradeSetup:
    if signal not in ("BUY", "SELL"):
        return TradeSetup(valid=False, reason="Señal inválida")
    if price <= 0 or atr <= 0:
        return TradeSetup(valid=False, reason="Datos insuficientes (price/atr)")
 
    sl_distance = atr * cfg.atr_sl_multiplier
    tp_distance = atr * cfg.atr_tp_multiplier
 
    if signal == "BUY":
        stop_loss = price - sl_distance
        take_profit = price + tp_distance
    else:
        stop_loss = price + sl_distance
        take_profit = price - tp_distance
 
    rr = tp_distance / sl_distance if sl_distance else 0.0
 
    return TradeSetup(
        valid=True,
        signal=signal,
        entry=round_price(spec, price),
        stop_loss=round_price(spec, stop_loss),
        take_profit=round_price(spec, take_profit),
        sl_distance=sl_distance,
        tp_distance=tp_distance,
        risk_reward=round(rr, 2),
        reason="Setup calculado por ATR",
    )