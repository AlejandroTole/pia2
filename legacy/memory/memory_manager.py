import json
import os
import uuid
from datetime import datetime


class MemoryManager:

    def __init__(self):
        print("🧠 Memory Manager iniciado")

        self.folder = "memory/storage"
        self.file = f"{self.folder}/pia_memory.json"
        self.create_storage()

    # ==================================
    # CREAR STORAGE
    # ==================================

    def create_storage(self):
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

        if not os.path.exists(self.file):
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=4)

    # ==================================
    # GUARDAR INFORMACION
    # ==================================

    def save(self, data):
        if data.get("type") == "trade_decision":
            signal = data.get("signal", "WAIT")
            price = data.get("entry_price", 0)

            if signal == "WAIT":
                print("⏸️ WAIT no guardado")
                return False

            if price <= 0:
                print("⚠️ Precio inválido")
                return False

        with open(self.file, "r", encoding="utf-8") as f:
            memory = json.load(f)

        data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        memory.append(data)

        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=4, ensure_ascii=False)

        return True

    # ==================================
    # LEER MEMORIA COMPLETA
    # ==================================

    def get_all(self):
        with open(self.file, "r", encoding="utf-8") as f:
            return json.load(f)

    # ==================================
    # GUARDAR OPERACION
    # ==================================

    def save_trade_decision(self, symbol, signal, confidence, price, stop_loss=0, take_profit=0):
        """
        Devuelve el trade_id generado (o None si no se guardó, ej. WAIT
        o precio inválido). Antes no devolvía ningún identificador —
        ahora es necesario para poder actualizar el resultado correcto
        más adelante sin ambigüedad.
        """
        trade_id = uuid.uuid4().hex

        trade = {
            "trade_id": trade_id,
            "type": "trade_decision",
            "symbol": symbol,
            "signal": signal,
            "confidence": confidence,
            "entry_price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "exit_price": 0,
            "result": "PENDING",
            "profit_loss": 0,
            "duration": 0,
        }

        saved = self.save(trade)

        if saved:
            print(f"💾 Trade guardado en memoria (id={trade_id})")
            return trade_id

        return None

    # ==================================
    # BUSCAR POR SIMBOLO
    # ==================================

    def search_symbol(self, symbol):
        memory = self.get_all()
        return [item for item in memory if item.get("symbol") == symbol]

    def search_signal(self, signal):
        memory = self.get_all()
        return [item for item in memory if item.get("signal") == signal]

    def search_confidence(self, minimum):
        memory = self.get_all()
        return [item for item in memory if float(item.get("confidence", 0)) >= float(minimum)]

    def recent(self, limit=5):
        memory = self.get_all()
        return list(reversed(memory))[:limit]

    # ==================================
    # OPERACIONES PENDIENTES
    # ==================================

    def pending_trades(self):
        memory = self.get_all()
        return [
            item for item in memory
            if item.get("type") == "trade_decision" and item.get("result") == "PENDING"
        ]

    # ==================================
    # ACTUALIZAR RESULTADO
    # ==================================

    def update_trade_result(self, trade_id, result, profit_loss, exit_price=0, duration=0):
        """
        Antes: buscaba por 'timestamp' (resolución de segundos), lo cual
        podía coincidir entre dos operaciones distintas guardadas casi al
        mismo tiempo y actualizar ambas por error. Ahora usa 'trade_id'
        (único por operación, generado en save_trade_decision).
        """
        memory = self.get_all()
        found = False

        for item in memory:
            if item.get("trade_id") == trade_id and item.get("type") == "trade_decision":
                item["result"] = result
                item["profit_loss"] = profit_loss
                item["exit_price"] = exit_price
                item["duration"] = duration
                found = True
                break

        if not found:
            print(f"⚠️ No se encontró trade_id={trade_id} para actualizar")
            return False

        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=4, ensure_ascii=False)

        print("🧠 Resultado actualizado")
        return True

    # ==================================
    # ESTADISTICAS DE APRENDIZAJE
    # ==================================

    def statistics(self):
        memory = self.get_all()

        total = 0
        wins = 0
        losses = 0
        profit = 0

        for item in memory:
            if item.get("type") == "trade_decision":
                result = item.get("result")

                if result in ["WIN", "LOSS"]:
                    total += 1
                    profit += item.get("profit_loss", 0)

                    if result == "WIN":
                        wins += 1
                    else:
                        losses += 1

        win_rate = 0
        if total > 0:
            win_rate = round(wins / total * 100, 2)

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_profit": round(profit, 2),
        }