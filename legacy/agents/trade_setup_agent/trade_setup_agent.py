from config import settings


class TradeSetupAgent:
    """
    Calcula el "plan de operación": precio de entrada, Stop Loss y
    Take Profit, basado en ATR y los multiplicadores configurados en
    settings.py.

    Este es el único lugar del sistema que debe calcular la distancia
    de SL/TP. RiskManager usa el sl_distance que este agente calcula
    (en vez de recalcularlo por su cuenta) para dimensionar el lote,
    evitando que ambos módulos puedan desincronizarse si los
    multiplicadores cambian en el futuro (por ejemplo, vía ajuste
    automático desde ai_brain).
    """

    def __init__(self):
        print("📋 Trade Setup Agent iniciado")

        self.sl_multiplier = settings.ATR_STOPLOSS_MULTIPLIER
        self.tp_multiplier = settings.ATR_TAKEPROFIT_MULTIPLIER

    def create_setup(self, market_data, confluence_data):
        # NOTA: se asume que confluence_data trae una clave "approved".
        # Pendiente de confirmar contra la salida real de ConfluenceAgent —
        # si esa clave no existe, esta condición siempre será False.
        if not confluence_data.get("approved"):
            return {
                "valid": False,
                "reason": "Sin confluencia suficiente",
            }

        signal = confluence_data.get("signal", "WAIT")
        price = market_data.get("price", 0)
        atr = market_data.get("atr", 0)

        if not price or not atr:
            return {
                "valid": False,
                "reason": "Datos de mercado insuficientes (price/atr)",
            }

        sl_distance = atr * self.sl_multiplier
        tp_distance = atr * self.tp_multiplier

        if signal == "BUY":
            stop_loss = price - sl_distance
            take_profit = price + tp_distance
        elif signal == "SELL":
            stop_loss = price + sl_distance
            take_profit = price - tp_distance
        else:
            return {
                "valid": False,
                "reason": "Señal inválida",
            }

        risk_reward_ratio = self.tp_multiplier / self.sl_multiplier

        return {
            "valid": True,
            "symbol": market_data.get("symbol"),
            "signal": signal,
            "entry": round(price, 5),
            "stop_loss": round(stop_loss, 5),
            "take_profit": round(take_profit, 5),
            "sl_distance": sl_distance,
            "tp_distance": tp_distance,
            "risk_reward": f"1:{risk_reward_ratio:.1f}",
            "confidence": confluence_data.get("confidence", 0),
            "reasons": confluence_data.get("reasons", []),
        }