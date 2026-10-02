import MetaTrader5 as mt5
from datetime import datetime

from config import settings


class TradeExecutor:
    """
    Ejecuta (o simula) una operación según el resultado del pipeline de
    decisión (Confluence -> TradeSetup -> Risk).

    Modo controlado por settings.ENABLE_AUTO_TRADE:
    - False (default actual): modo SIMULADO — no se envía ninguna orden a
      MT5, solo se registra la decisión en memoria/log. Permite validar
      la lógica de todo el pipeline sin generar órdenes, incluso estando
      conectado a la cuenta demo.
    - True: se envía la orden real a MT5 (a la cuenta que tengas
      conectada — demo o real, según lo logueado en el terminal).
      Requiere que RiskManager haya aprobado con un volumen válido y que
      TradeSetupAgent haya calculado un setup válido (SL/TP).
    """

    def __init__(self, memory=None):
        print("⚙️ Trade Executor iniciado")
        self.memory = memory
        self.auto_trade_enabled = settings.ENABLE_AUTO_TRADE

        mode = "REAL (envía órdenes a MT5)" if self.auto_trade_enabled else "SIMULADO (solo registro)"
        print(f"   Modo: {mode}")

    def execute(self, symbol, confluence_data, risk_data, trade_setup_data=None):
        result = {
            "executed": False,
            "symbol": symbol,
            "signal": "WAIT",
            "mode": "auto" if self.auto_trade_enabled else "simulated",
            "reason": "",
        }

        if not risk_data.get("approved", False):
            result["reason"] = "Risk rechazó operación"
            return result

        signal = confluence_data.get("signal", "WAIT")
        confidence = confluence_data.get("confidence", 0)

        if signal == "WAIT":
            result["reason"] = "Sin señal válida"
            return result

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            result["reason"] = "No hay precio MT5"
            return result

        price = tick.ask if signal == "BUY" else tick.bid

        if self.auto_trade_enabled:
            return self._execute_real(
                symbol, signal, price, confidence, risk_data, trade_setup_data, result
            )

        return self._execute_simulated(symbol, signal, price, confidence, trade_setup_data, result)

    # ==================================
    # MODO SIMULADO (sin orden real a MT5)
    # ==================================

    def _execute_simulated(self, symbol, signal, price, confidence, trade_setup_data, result):
        print("\n🧪 SIMULATED TRADE (ENABLE_AUTO_TRADE=False)")
        print(f"📌 {signal} {symbol}")
        print(f"📌 Entrada: {price}")
        print(f"📌 Confianza: {confidence}")

        # Antes se guardaba con stop_loss=0, take_profit=0 (valores por
        # defecto) aunque TradeSetupAgent ya los tuviera calculados.
        stop_loss = trade_setup_data.get("stop_loss", 0) if trade_setup_data else 0
        take_profit = trade_setup_data.get("take_profit", 0) if trade_setup_data else 0

        trade_id = None
        timestamp = None
        if self.memory:
            # save_trade_decision ahora devuelve el trade_id generado —
            # antes no se capturaba nada, y no había forma de referenciar
            # esta operación después para actualizar su resultado.
            trade_id = self.memory.save_trade_decision(
                symbol, signal, confidence, price, stop_loss, take_profit
            )
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            print("⚠️ TradeExecutor sin memoria conectada — la decisión NO se guardó")

        result.update({
            "executed": True,
            "signal": signal,
            "price": price,
            "confidence": confidence,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "trade_id": trade_id,
            "timestamp": timestamp,
            "reason": "Operación simulada guardada en memoria (sin orden real a MT5)",
        })
        return result

    # ==================================
    # MODO REAL (envía orden a MT5)
    # ==================================

    def _execute_real(self, symbol, signal, price, confidence, risk_data, trade_setup_data, result):
        volume = risk_data.get("volume", 0)

        if not volume or volume <= 0:
            result["reason"] = "Volumen inválido calculado por RiskManager"
            return result

        if not trade_setup_data or not trade_setup_data.get("valid"):
            result["reason"] = "Trade setup inválido, no se puede construir SL/TP"
            return result

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            result["reason"] = f"No se encontró información de {symbol}"
            return result

        digits = symbol_info.digits
        stop_loss = round(trade_setup_data["stop_loss"], digits)
        take_profit = round(trade_setup_data["take_profit"], digits)

        # Verificación de distancia mínima permitida por el broker
        point = symbol_info.point
        min_dist = getattr(symbol_info, "trade_stops_level", 0) * point

        if signal == "BUY":
            if (price - stop_loss) < min_dist:
                stop_loss = round(price - min_dist, digits)
            if (take_profit - price) < min_dist:
                take_profit = round(price + min_dist, digits)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            if (stop_loss - price) < min_dist:
                stop_loss = round(price + min_dist, digits)
            if (price - take_profit) < min_dist:
                take_profit = round(price - min_dist, digits)
            order_type = mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 50,
            "magic": settings.MAGIC_NUMBER,
            "comment": f"PIA_{signal}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        order_result = mt5.order_send(request)

        if order_result is None or order_result.retcode != mt5.TRADE_RETCODE_DONE:
            error = order_result.comment if order_result else mt5.last_error()
            result["reason"] = f"Orden rechazada por MT5: {error}"
            return result

        print("\n✅ ORDEN REAL EJECUTADA")
        print(f"📌 {signal} {symbol} | Volumen: {volume} | SL: {stop_loss} | TP: {take_profit}")

        timestamp = None
        trade_id = None
        if self.memory:
            trade_id = self.memory.save_trade_decision(
                symbol, signal, confidence, order_result.price, stop_loss, take_profit
            )
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result.update({
            "executed": True,
            "signal": signal,
            "price": order_result.price,
            "volume": volume,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "ticket": order_result.order,
            "trade_id": trade_id,
            "confidence": confidence,
            "timestamp": timestamp,
            "reason": "Orden real enviada a MT5",
        })
        return result