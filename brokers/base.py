
"""Interfaz de broker.
 
Toda la interacción con el mercado pasa por esta interfaz abstracta. Así el
resto del sistema (riesgo, ejecución, orquestador, backtesting) no depende de
MetaTrader5 directamente, y podemos:
  - usar MT5Broker en producción (Windows), y
  - usar PaperBroker en tests/backtesting (cualquier plataforma, sin MT5).
 
Esto es clave porque la librería MetaTrader5 solo existe en Windows; con esta
abstracción la lógica pura se prueba en Linux/CI con el PaperBroker.
"""
 
from __future__ import annotations
 
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
 
import pandas as pd
 
from pia2.market.instruments import SymbolSpec
 
 
@dataclass
class Tick:
    symbol: str
    bid: float
    ask: float
    time: datetime
 
    @property
    def spread_points(self) -> float:
        return self.ask - self.bid
 
 
@dataclass
class AccountInfo:
    balance: float
    equity: float
    currency: str
    leverage: int = 100
    login: int = 0
    margin_free: float | None = None
    margin_level: float | None = None
 
 
@dataclass
class Position:
    ticket: int
    symbol: str
    direction: str  # "BUY" | "SELL"
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    profit: float
    magic: int = 0
 
 
@dataclass
class OrderResult:
    ok: bool
    ticket: int | None = None
    price: float | None = None
    reason: str = ""
 
 
@dataclass
class ClosedDeal:
    ticket: int
    symbol: str
    direction: str
    volume: float
    entry_price: float
    exit_price: float
    profit: float
    close_time: datetime
    magic: int = 0
    commission: float = 0.0
    swap: float = 0.0
    fee: float = 0.0
 
 
class BrokerInterface(ABC):
    """Contrato mínimo que debe cumplir cualquier broker usado por PIA."""
 
    @abstractmethod
    def connect(self) -> bool: ...
 
    @abstractmethod
    def disconnect(self) -> None: ...
 
    @abstractmethod
    def is_connected(self) -> bool: ...
 
    @abstractmethod
    def account(self) -> AccountInfo | None: ...
 
    @abstractmethod
    def symbol_spec(self, symbol: str) -> SymbolSpec | None: ...
 
    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame | None:
        """Devuelve un DataFrame con columnas: time, open, high, low, close, (volume)."""
 
    @abstractmethod
    def get_tick(self, symbol: str) -> Tick | None: ...
 
    @abstractmethod
    def open_positions(self, symbol: str | None = None) -> list[Position]: ...

    @abstractmethod
    def modify_position_sl(self, ticket: int, stop_loss: float) -> bool:
        """Mueve el SL de una posición abierta. True si el broker lo aceptó."""
        ...

    @abstractmethod
    def close_position(self, ticket: int) -> bool:
        """Cierra una posición a mercado. True si se cerró."""
        ...

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        magic: int,
        comment: str = "",
    ) -> OrderResult: ...
 
    @abstractmethod
    def closed_deals_since(self, since: datetime, magic: int | None = None) -> list[ClosedDeal]:
        """Operaciones cerradas por el broker desde 'since' (para P/L real)."""