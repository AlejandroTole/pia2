"""Broker real sobre MetaTrader 5.
 
IMPORTANTE: la librería `MetaTrader5` solo funciona en Windows. Por eso el
import es perezoso (dentro de connect), y este módulo se puede importar en
cualquier plataforma sin romper; solo fallará al intentar CONECTAR si MT5 no
está disponible. En Linux/CI se usa PaperBroker.
"""
 
from __future__ import annotations
 
from datetime import datetime, timedelta, timezone
 
import pandas as pd
 
from pia2.brokers.base import (
    AccountInfo,
    BrokerInterface,
    ClosedDeal,
    OrderResult,
    Position,
    Tick,
)
from pia2.market.instruments import SymbolSpec, normalize_volume, round_price


def select_filling_mode(mt5, filling_flags, trade_execution=None) -> int:
    """Elige un modo de ejecución concreto a partir del bitmask del símbolo.

    `symbol_info.filling_mode` es una máscara de bits (puede combinar varios
    modos permitidos); en cambio `type_filling` del request necesita UN modo.
    Los flags de símbolo son FOK=1 e IOC=2; los valores ORDER_FILLING son una
    enumeración distinta. RETURN está permitido salvo en ejecución de mercado.
    """
    if filling_flags is None:
        return mt5.ORDER_FILLING_IOC
    try:
        flags = int(filling_flags)
    except (TypeError, ValueError):
        return mt5.ORDER_FILLING_IOC
    if flags & 1:
        return mt5.ORDER_FILLING_FOK
    if flags & 2:
        return mt5.ORDER_FILLING_IOC
    market_execution = getattr(mt5, "SYMBOL_TRADE_EXECUTION_MARKET", 2)
    if trade_execution != market_execution:
        return mt5.ORDER_FILLING_RETURN
    return mt5.ORDER_FILLING_IOC


class MT5Broker(BrokerInterface):
    def __init__(
        self,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        account_type_required: str = "demo",
        symbols: list[str] | None = None,
        default_deviation: int = 50,
    ):
        self.login = login
        self.password = password
        self.server = server
        self.account_type_required = account_type_required
        self.symbols = symbols or []
        self.default_deviation = int(default_deviation)
        self._mt5 = None
        self._connected = False
 
    def _ensure_lib(self):
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5  # noqa: import perezoso (solo Windows)
            except ImportError as exc:  # pragma: no cover - depende de plataforma
                raise RuntimeError(
                    "MetaTrader5 no está disponible. Instálalo en Windows: "
                    "pip install MetaTrader5"
                ) from exc
            self._mt5 = mt5
        return self._mt5
 
    def _timeframe(self, timeframe: str):
        mt5 = self._ensure_lib()
        mapping = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        return mapping[timeframe]
 
    def connect(self) -> bool:
        mt5 = self._ensure_lib()
        if self.login and self.password and self.server:
            ok = mt5.initialize(login=self.login, password=self.password, server=self.server)
        else:
            ok = mt5.initialize()
        if not ok:
            self._connected = False
            return False

        account = mt5.account_info()
        terminal = mt5.terminal_info()
        demo_mode = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
        account_mode = getattr(account, "trade_mode", None) if account else None
        account_trade_allowed = getattr(account, "trade_allowed", False) if account else False
        terminal_trade_allowed = getattr(terminal, "trade_allowed", False) if terminal else False

        expected_mode = demo_mode if self.account_type_required == "demo" else getattr(
            mt5, "ACCOUNT_TRADE_MODE_REAL", 2
        )
        if account is None or account_mode != expected_mode:
            self.disconnect()
            return False
        if not account_trade_allowed or not terminal_trade_allowed:
            self.disconnect()
            return False

        for symbol in self.symbols:
            if not mt5.symbol_select(symbol, True):
                self.disconnect()
                return False
            info = mt5.symbol_info(symbol)
            if info is None:
                self.disconnect()
                return False
            disabled_mode = getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", None)
            if (
                getattr(info, "trade_mode", None) is not None
                and disabled_mode is not None
                and info.trade_mode == disabled_mode
            ):
                self.disconnect()
                return False
            if (
                getattr(info, "trade_stops_level", None) is None
                or getattr(info, "trade_freeze_level", None) is None
            ):
                self.disconnect()
                return False

        self._connected = True
        print(
            f"MT5 verificado | login={getattr(account, 'login', self.login)} | "
            f"servidor={getattr(account, 'server', self.server or 'desconocido')} | "
            f"cuenta={self.account_type_required}"
        )
        return True
 
    def disconnect(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()
        self._connected = False
 
    def is_connected(self) -> bool:
        if not self._connected or self._mt5 is None:
            return False
        return self._mt5.account_info() is not None
 
    def account(self) -> AccountInfo | None:
        mt5 = self._ensure_lib()
        info = mt5.account_info()
        if info is None:
            return None
        return AccountInfo(
            balance=info.balance,
            equity=info.equity,
            currency=info.currency,
            leverage=getattr(info, "leverage", 100) or 100,
            login=info.login,
            margin_free=getattr(info, "margin_free", None),
            margin_level=getattr(info, "margin_level", None),
        )

    def estimate_margin(
        self, symbol: str, direction: str, volume: float, price: float
    ) -> float | None:
        mt5 = self._ensure_lib()
        order_type = mt5.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        try:
            margin = mt5.order_calc_margin(order_type, symbol, volume, price)
        except Exception:
            return None
        return float(margin) if margin is not None else None
 
    def symbol_spec(self, symbol: str) -> SymbolSpec | None:
        mt5 = self._ensure_lib()
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return SymbolSpec(
            name=symbol,
            digits=info.digits,
            point=info.point,
            tick_size=info.trade_tick_size or info.point,
            tick_value=info.trade_tick_value,
            contract_size=info.trade_contract_size,
            volume_min=info.volume_min or 0.01,
            volume_max=info.volume_max or 100.0,
            volume_step=info.volume_step or 0.01,
            trade_stops_level=getattr(info, "trade_stops_level", 0),
        )
 
    def get_candles(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame | None:
        mt5 = self._ensure_lib()
        # La posición 0 es la vela actualmente en formación.
        rates = mt5.copy_rates_from_pos(symbol, self._timeframe(timeframe), 1, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df
 
    def get_tick(self, symbol: str) -> Tick | None:
        mt5 = self._ensure_lib()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return Tick(
            symbol=symbol,
            bid=tick.bid,
            ask=tick.ask,
            time=datetime.fromtimestamp(tick.time),
        )
 
    def open_positions(self, symbol: str | None = None) -> list[Position]:
        mt5 = self._ensure_lib()
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []
        result = []
        for p in positions:
            direction = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
            result.append(
                Position(
                    ticket=p.ticket,
                    symbol=p.symbol,
                    direction=direction,
                    volume=p.volume,
                    entry_price=p.price_open,
                    stop_loss=p.sl,
                    take_profit=p.tp,
                    profit=p.profit,
                    magic=p.magic,
                )
            )
        return result
 
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
        mt5 = self._ensure_lib()
        spec = self.symbol_spec(symbol)
        tick = self.get_tick(symbol)
        if spec is None or tick is None:
            return OrderResult(ok=False, reason="Sin spec o tick del símbolo")

        info = mt5.symbol_info(symbol)
        if info is None:
            return OrderResult(ok=False, reason=f"Sin info del símbolo {symbol}")

        volume = normalize_volume(spec, volume)
        is_buy = direction.upper() == "BUY"
        price = tick.ask if is_buy else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

        # Respetar la distancia mínima de stops del broker.
        min_dist = spec.trade_stops_level * spec.point
        sl = round_price(spec, stop_loss)
        tp = round_price(spec, take_profit)
        if is_buy:
            if price - sl < min_dist:
                sl = round_price(spec, price - min_dist)
            if tp - price < min_dist:
                tp = round_price(spec, price + min_dist)
        else:
            if sl - price < min_dist:
                sl = round_price(spec, price + min_dist)
            if price - tp < min_dist:
                tp = round_price(spec, price - min_dist)

        filling_mode = select_filling_mode(
            mt5,
            getattr(info, "filling_mode", None),
            getattr(info, "trade_exemode", None),
        )

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.default_deviation,
            "magic": magic,
            "comment": comment or f"PIA_{direction.upper()}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        order_check = mt5.order_check(request)
        if order_check is None or getattr(order_check, "retcode", None) != mt5.TRADE_RETCODE_DONE:
            reason = getattr(order_check, "comment", None) or str(mt5.last_error())
            text = (reason or "").lower()
            if "requote" in text or "off quote" in text or "off quotes" in text:
                result = mt5.order_send(request)
                if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                    return OrderResult(ok=True, ticket=result.order, price=result.price)
            return OrderResult(ok=False, reason=f"Orden rechazada: {reason}")

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            reason = getattr(result, "comment", None) or str(mt5.last_error())
            text = (reason or "").lower()
            if "requote" in text or "off quote" in text or "off quotes" in text:
                result = mt5.order_send(request)
                if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                    return OrderResult(ok=True, ticket=result.order, price=result.price)
            return OrderResult(ok=False, reason=f"Orden rechazada: {reason}")

        return OrderResult(ok=True, ticket=result.order, price=result.price)

    def closed_deals_since(self, since: datetime, magic: int | None = None) -> list[ClosedDeal]:
        mt5 = self._ensure_lib()
        try:
            now = datetime.now(timezone.utc)
            deals = mt5.history_deals_get(since, now + timedelta(days=1))
        except Exception as exc:
            # MT5 puede fallar con fechas inválidas o sin historial disponible
            print(f"[Advertencia] Error al obtener historial de deals: {exc}")
            return []
        if deals is None:
            return []
        result = []
        for d in deals:
            # DEAL_ENTRY_OUT marca el cierre de una posición.
            if getattr(d, "entry", None) != mt5.DEAL_ENTRY_OUT:
                continue
            if magic is not None and d.magic != magic:
                continue
            direction = "SELL" if d.type == mt5.DEAL_TYPE_BUY else "BUY"
            result.append(
                ClosedDeal(
                    ticket=d.position_id,
                    symbol=d.symbol,
                    direction=direction,
                    volume=d.volume,
                    entry_price=0.0,
                    exit_price=d.price,
                    profit=d.profit,
                    close_time=datetime.fromtimestamp(d.time, tz=timezone.utc),
                    magic=d.magic,
                    commission=float(getattr(d, "commission", 0.0) or 0.0),
                    swap=float(getattr(d, "swap", 0.0) or 0.0),
                    fee=float(getattr(d, "fee", 0.0) or 0.0),
                )
            )
        return result
