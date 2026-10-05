"""Broker simulado para pruebas y validación sin MetaTrader5."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from pia2.brokers.base import (
    AccountInfo,
    BrokerInterface,
    ClosedDeal,
    OrderResult,
    Position,
    Tick,
)
from pia2.market.instruments import SymbolSpec, money_profit


class PaperBroker(BrokerInterface):
    """Broker ligero con comportamiento de paper-trading para CI y tests."""

    def __init__(self, balance: float = 10000.0, currency: str = "USD", leverage: int = 100):
        self.balance = float(balance)
        self.currency = currency
        self.leverage = int(leverage)
        self._connected = False
        self._specs: dict[str, SymbolSpec] = {}
        self._candles: dict[str, pd.DataFrame] = {}
        self._ticks: dict[str, Tick] = {}
        self._positions: list[Position] = []
        self._closed: list[ClosedDeal] = []
        self._next_ticket = 1

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def account(self) -> AccountInfo | None:
        if not self._connected:
            return None
        return AccountInfo(
            balance=self.balance,
            equity=self.balance,
            currency=self.currency,
            leverage=self.leverage,
            login=0,
            margin_free=self.balance * 0.5,
            margin_level=100.0,
        )

    def symbol_spec(self, symbol: str) -> SymbolSpec | None:
        return self._specs.get(symbol)

    def set_spec(self, symbol_or_spec: str | SymbolSpec, spec: SymbolSpec | None = None) -> None:
        if isinstance(symbol_or_spec, SymbolSpec):
            self._specs[symbol_or_spec.name] = symbol_or_spec
            return
        if spec is None:
            raise TypeError("set_spec require a SymbolSpec or a (symbol, spec) pair")
        self._specs[str(symbol_or_spec)] = spec

    def set_candles(self, symbol: str, df: pd.DataFrame) -> None:
        self._candles[symbol] = df.copy()

    def set_tick(self, symbol: str, bid: float, ask: float, time: datetime | None = None) -> None:
        self._ticks[symbol] = Tick(symbol=symbol, bid=float(bid), ask=float(ask), time=time or datetime.now(timezone.utc))

    def get_candles(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame | None:
        df = self._candles.get(symbol)
        if df is None or df.empty:
            return None
        out = df.copy()
        if "time" in out.columns:
            out["time"] = pd.to_datetime(out["time"])
        return out.tail(count)

    def get_tick(self, symbol: str) -> Tick | None:
        return self._ticks.get(symbol)

    def open_positions(self, symbol: str | None = None) -> list[Position]:
        if symbol is None:
            return list(self._positions)
        return [p for p in self._positions if p.symbol == symbol]

    def modify_position_sl(self, ticket: int, stop_loss: float) -> bool:
        position = next((p for p in self._positions if p.ticket == ticket), None)
        if position is None:
            return False
        position.stop_loss = float(stop_loss)
        return True

    def close_position(self, ticket: int) -> bool:
        position = next((p for p in self._positions if p.ticket == ticket), None)
        if position is None:
            return False
        tick = self.get_tick(position.symbol)
        spec = self.symbol_spec(position.symbol)
        if tick is None or spec is None:
            return False

        exit_price = tick.bid if position.direction == "BUY" else tick.ask
        profit = money_profit(
            spec,
            position.direction,
            position.entry_price,
            exit_price,
            position.volume,
        )
        self._positions.remove(position)
        self._closed.append(
            ClosedDeal(
                ticket=position.ticket,
                symbol=position.symbol,
                direction=position.direction,
                volume=position.volume,
                entry_price=position.entry_price,
                exit_price=exit_price,
                profit=profit,
                close_time=tick.time,
                magic=position.magic,
            )
        )
        self.balance += profit
        return True

    def place_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        magic: int,
        comment: str = "",
    ) -> OrderResult:
        spec = self.symbol_spec(symbol)
        if spec is None:
            return OrderResult(ok=False, reason=f"Sin spec para {symbol}")
        tick = self.get_tick(symbol)
        if tick is None:
            return OrderResult(ok=False, reason=f"Sin tick para {symbol}")

        price = tick.ask if direction.upper() == "BUY" else tick.bid
        ticket = self._next_ticket
        self._next_ticket += 1
        pos = Position(
            ticket=ticket,
            symbol=symbol,
            direction=direction.upper(),
            volume=float(volume),
            entry_price=float(price),
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
            profit=0.0,
            magic=int(magic),
        )
        self._positions.append(pos)
        return OrderResult(ok=True, ticket=ticket, price=price)

    def closed_deals_since(self, since: datetime, magic: int | None = None) -> list[ClosedDeal]:
        deals = []
        for trade in self._closed:
            if trade.close_time >= since:
                if magic is None or trade.magic == magic:
                    deals.append(trade)
        return deals

    def add_closed_deal(
        self,
        ticket: int,
        symbol: str,
        direction: str,
        volume: float,
        entry_price: float,
        exit_price: float,
        profit: float,
        close_time: datetime,
        magic: int = 0,
    ) -> None:
        self._closed.append(
            ClosedDeal(
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                volume=volume,
                entry_price=entry_price,
                exit_price=exit_price,
                profit=profit,
                close_time=close_time,
                magic=magic,
            )
        )

    def estimate_margin(self, symbol: str, direction: str, volume: float, price: float) -> float | None:
        spec = self.symbol_spec(symbol)
        if spec is None:
            return None
        return abs(float(volume) * spec.contract_size * float(price) / max(self.leverage, 1))
