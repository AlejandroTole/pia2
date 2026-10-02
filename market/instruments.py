"""Especificaciones de instrumentos y cálculo correcto de P/L.
 
La v1 calculaba pips con `* 10000` fijo, lo cual es incorrecto para pares con
JPY (2-3 dígitos) y para el oro (XAUUSD). Aquí el cálculo se hace SIEMPRE con
las especificaciones reales del símbolo (provistas por el broker), no con una
constante mágica.
"""
 
from __future__ import annotations
 
from dataclasses import dataclass
import math
 
 
@dataclass
class SymbolSpec:
    """Especificaciones de un símbolo tal como las expone el broker (MT5).
 
    - digits: número de decimales del precio.
    - point: valor de 1 "point" (el menor incremento de precio).
    - tick_size / tick_value: tamaño y valor monetario de 1 tick por 1 lote.
    - contract_size: unidades por lote estándar.
    - volume_min / volume_max / volume_step: límites de volumen del broker.
    """
 
    name: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    trade_stops_level: int = 0
 
    @property
    def pip_size(self) -> float:
        """Tamaño de 1 pip.
 
        Convención estándar: para símbolos de 5 o 3 dígitos, 1 pip = 10 points
        (el último dígito es una fracción de pip). Para 4 o 2 dígitos, 1 pip =
        1 point. Cubre correctamente EURUSD (5), USDJPY (3), XAUUSD (2), etc.
        """
        if self.digits in (3, 5):
            return self.point * 10
        return self.point
 
 
def money_profit(spec: SymbolSpec, direction: str, entry: float, exit_price: float,
                 volume: float) -> float:
    """P/L en dinero de la cuenta para una operación cerrada.
 
    Usa tick_value/tick_size reales del símbolo, no una constante. `direction`
    es "BUY" o "SELL".
    """
    if spec.tick_size <= 0 or spec.tick_value <= 0:
        raise ValueError(f"tick_size/tick_value inválidos para {spec.name}")
 
    price_diff = exit_price - entry if direction.upper() == "BUY" else entry - exit_price
    ticks = price_diff / spec.tick_size
    return ticks * spec.tick_value * volume
 
 
def price_to_pips(spec: SymbolSpec, price_distance: float) -> float:
    """Convierte una distancia de precio a pips según el símbolo."""
    if spec.pip_size <= 0:
        return 0.0
    return price_distance / spec.pip_size
 
 
def normalize_volume(spec: SymbolSpec, raw_volume: float) -> float:
    """Ajusta un volumen crudo al step/min/max permitidos por el símbolo."""
    step = spec.volume_step or 0.01
    # Nunca redondear hacia arriba: el volumen normalizado no debe superar
    # accidentalmente el riesgo calculado.
    volume = math.floor((raw_volume / step) + 1e-12) * step
    volume = max(spec.volume_min, volume)
    volume = min(volume, spec.volume_max)
    # Redondeo a la precisión del step para evitar arrastre de floats.
    decimals = max(0, len(str(step).split(".")[-1])) if "." in str(step) else 0
    return round(volume, decimals)
 
 
def round_price(spec: SymbolSpec, price: float) -> float:
    """Redondea un precio a los dígitos del símbolo (no fijo a 5 como la v1)."""
    return round(price, spec.digits)