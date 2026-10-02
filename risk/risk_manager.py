"""Cálculo de tamaño de posición según el riesgo configurado.
 
Dado el balance, la distancia de Stop Loss y las especificaciones del símbolo,
calcula el volumen (lote) para que la pérdida máxima al tocar el SL sea igual
al porcentaje de riesgo configurado. Usa las specs reales del símbolo (no
constantes mágicas).
"""
 
from __future__ import annotations
 
from dataclasses import dataclass
 
from pia2.market.instruments import SymbolSpec, normalize_volume
 
 
@dataclass
class PositionSizing:
    approved: bool
    volume: float = 0.0
    risk_amount: float = 0.0
    target_risk_amount: float = 0.0
    sl_distance: float = 0.0
    reason: str = ""
 
 
class RiskManager:
    def __init__(self, risk_per_trade_pct: float, max_margin_per_trade_usd: float = 500.0):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_margin_per_trade_usd = max_margin_per_trade_usd
 
    def size(
        self,
        spec: SymbolSpec,
        balance: float,
        sl_distance: float,
        account_leverage: int = 100,
        margin_estimator=None,
        margin_free: float | None = None,
        margin_level: float | None = None,
    ) -> PositionSizing:
        if balance <= 0:
            return PositionSizing(False, reason="Balance inválido")
        if sl_distance <= 0:
            return PositionSizing(False, reason="Distancia de SL inválida")
        if spec.tick_size <= 0 or spec.tick_value <= 0:
            return PositionSizing(False, reason=f"Specs inválidas para {spec.name}")

        risk_amount = balance * (self.risk_per_trade_pct / 100.0)

        sl_ticks = sl_distance / spec.tick_size
        loss_per_lot = sl_ticks * spec.tick_value
        if loss_per_lot <= 0:
            return PositionSizing(False, reason="Pérdida por lote no calculable")

        raw_volume = risk_amount / loss_per_lot
        volume = normalize_volume(spec, raw_volume)

        if volume <= 0:
            return PositionSizing(False, reason="Volumen calculado es 0")

        actual_risk_amount = round(volume * loss_per_lot, 2)
        if actual_risk_amount > risk_amount * 1.25:
            return PositionSizing(
                False,
                volume=volume,
                risk_amount=actual_risk_amount,
                target_risk_amount=risk_amount,
                sl_distance=sl_distance,
                reason=(
                    f"Riesgo real ${actual_risk_amount:.2f} excede 1.25x "
                    f"el objetivo ${risk_amount:.2f} por lote mínimo"
                ),
            )

        leverage = max(1, int(account_leverage or 1))
        position_notional = volume * spec.contract_size
        estimated_margin = (
            margin_estimator(volume)
            if margin_estimator is not None
            else position_notional / leverage
        )
        if estimated_margin is None or estimated_margin <= 0:
            return PositionSizing(
                False,
                volume=volume,
                risk_amount=actual_risk_amount,
                target_risk_amount=risk_amount,
                reason="Margen no calculable por el broker",
            )
        if margin_free is not None and estimated_margin > margin_free:
            return PositionSizing(
                False,
                volume=volume,
                risk_amount=actual_risk_amount,
                target_risk_amount=risk_amount,
                reason=(
                    f"Margen estimado ${estimated_margin:.2f} excede margen libre "
                    f"${margin_free:.2f}"
                ),
            )
        if margin_level is not None and margin_level < 0:
            return PositionSizing(
                False,
                volume=volume,
                risk_amount=actual_risk_amount,
                target_risk_amount=risk_amount,
                reason=f"Margen de cuenta inválido ({margin_level:.2f}%)",
            )
        if estimated_margin > self.max_margin_per_trade_usd:
            return PositionSizing(
                False,
                risk_amount=actual_risk_amount,
                target_risk_amount=risk_amount,
                reason=(
                    f"Margen estimado ${estimated_margin:.2f} excede máximo "
                    f"${self.max_margin_per_trade_usd:.2f} (lev {leverage}:1)"
                ),
            )

        return PositionSizing(
            approved=True,
            volume=volume,
            risk_amount=actual_risk_amount,
            target_risk_amount=risk_amount,
            sl_distance=sl_distance,
            reason=(
                f"Riesgo real ${actual_risk_amount:.2f} "
                f"(objetivo {self.risk_per_trade_pct}% = ${risk_amount:.2f}) -> "
                f"{volume} lotes | margen est. ${estimated_margin:.2f} (lev {leverage}:1)"
            ),
        )