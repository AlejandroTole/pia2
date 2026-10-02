import json
import os

import pandas as pd

try:
    import MetaTrader5 as mt5
except ModuleNotFoundError:  # pragma: no cover - depende del entorno local de MT5
    mt5 = None

from config.loader import load_config
from pia2.strategy.indicators import add_indicators


class MultiHistoricalBuilder:

    def __init__(self, config=None, output_folder: str = "data/historical/features"):
        print("📚 Multi Historical Builder iniciado")

        self.config = config or load_config()
        self.output_folder = output_folder
        self.min_future_move_atr_ratio = self.config.historical.min_future_move_atr_ratio
        os.makedirs(self.output_folder, exist_ok=True)

    def prepare_feature_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        if frame.empty:
            return frame

        if "time" in frame.columns:
            frame["time"] = pd.to_datetime(frame["time"], errors="coerce")

        frame = add_indicators(frame, self.config.indicators)
        frame["trend"] = frame.apply(
            lambda row: "Alcista" if row["EMA_FAST"] > row["EMA_SLOW"] else "Bajista",
            axis=1,
        )

        future = frame["close"].shift(-4)
        frame["future_move"] = future - frame["close"]
        min_move = frame["ATR"] * self.min_future_move_atr_ratio

        frame["future_result"] = None
        frame.loc[frame["future_move"] > min_move, "future_result"] = "BUY"
        frame.loc[frame["future_move"] < -min_move, "future_result"] = "SELL"
        return frame

    def download_symbol(self, symbol, candles=50000):
        print("\n==============================")
        print(f"📥 Descargando {symbol}")
        print("==============================")

        if mt5 is None:
            raise RuntimeError("MetaTrader5 no está disponible en este entorno; no se puede descargar el histórico.")

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 1, candles)

        if rates is None:
            print(f"❌ No hay datos para {symbol}")
            return False

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = self.prepare_feature_frame(df)
        df = df.dropna(subset=["time", "close", "RSI", "ATR", "trend", "future_result"]).copy()

        data = df.to_dict(orient="records")

        filename = os.path.join(self.output_folder, f"{symbol}.json")

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)

        print(f"✅ {symbol}: {len(data)} patrones guardados")
        return True

    def build_all(self, symbols):
        for symbol in symbols:
            self.download_symbol(symbol)