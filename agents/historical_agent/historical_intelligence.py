import json
import os

from config import settings


class HistoricalIntelligence:
    """
    Compara el escenario de mercado actual (símbolo, tendencia, RSI) contra
    patrones históricos descargados de MT5 y procesados por
    MultiHistoricalBuilder, buscando qué tan seguido situaciones similares
    terminaron en BUY o SELL.

    Fuente de datos: data/historical/features/{symbol}.json — un archivo
    por símbolo, generado por MultiHistoricalBuilder. Antes este archivo
    leía un JSON combinado más viejo (market_history_features.json) que
    no tenía el campo "trend" ni estaba separado por símbolo.
    """

    def __init__(self):
        print("🔎 Historical Intelligence iniciado")

        self.features_folder = "data/historical/features"
        self._cache = {}  # symbol -> lista de patrones (se carga una vez por símbolo)

    # ==================================
    # CARGAR HISTÓRICO (por símbolo, con caché)
    # ==================================

    def _load_symbol_history(self, symbol):
        if symbol in self._cache:
            return self._cache[symbol]

        path = os.path.join(self.features_folder, f"{symbol}.json")

        if not os.path.exists(path):
            print(f"⚠️ No existe histórico para {symbol} ({path})")
            self._cache[symbol] = []
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"📚 Histórico cargado para {symbol}: {len(data)} patrones")
            self._cache[symbol] = data
            return data
        except Exception as e:
            print(f"❌ Error cargando histórico de {symbol}: {e}")
            self._cache[symbol] = []
            return []

    # ==================================
    # ANALISIS HISTORICO
    # ==================================

    def analyze(self, market_data):
        empty_result = {
            "bias": "NONE",
            "buy_probability": 0,
            "sell_probability": 0,
            "patterns": 0,
            "average_move": 0,
            "confidence": 0,
        }

        symbol = market_data.get("symbol")
        trend = market_data.get("trend")
        rsi = market_data.get("rsi", 50)

        if not symbol:
            return empty_result

        history = self._load_symbol_history(symbol)

        if not history:
            return empty_result

        matches = []

        # Ya no se filtra por "symbol" dentro de cada registro — cada
        # archivo ya corresponde a un solo símbolo.
        for item in history:
            item_trend = item.get("trend")
            item_rsi = item.get("RSI", 50)

            if item_trend == trend:
                if abs(float(item_rsi) - float(rsi)) <= settings.HISTORICAL_RSI_TOLERANCE:
                    matches.append(item)

        total = len(matches)

        if total == 0:
            return empty_result

        buys = 0
        sells = 0
        total_move = 0

        for item in matches:
            result = item.get("future_result")
            if result == "BUY":
                buys += 1
            elif result == "SELL":
                sells += 1

            total_move += float(item.get("future_move", 0))

        buy_probability = round((buys / total) * 100, 2)
        sell_probability = round((sells / total) * 100, 2)

        if buy_probability > sell_probability:
            bias = "BUY"
        elif sell_probability > buy_probability:
            bias = "SELL"
        else:
            bias = "NONE"

        raw_confidence = round(abs(buy_probability - sell_probability), 2)

        # Protección contra sobreconfianza con muestra chica (igual que
        # antes): si no hay suficientes patrones, la confianza se fuerza
        # a 0 aunque el porcentaje parezca extremo.
        confidence = raw_confidence if total >= settings.MIN_HISTORICAL_PATTERNS else 0

        if total < settings.MIN_HISTORICAL_PATTERNS:
            print(
                f"⚠️ Histórico {symbol}: solo {total} patrones similares "
                f"(mínimo {settings.MIN_HISTORICAL_PATTERNS}) — confianza forzada a 0"
            )

        return {
            "bias": bias,
            "buy_probability": buy_probability,
            "sell_probability": sell_probability,
            "patterns": total,
            "average_move": round(total_move / total, 6),
            "confidence": confidence,
            "raw_confidence": raw_confidence,
        }