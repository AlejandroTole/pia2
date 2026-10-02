import ta


class TechnicalAnalysis:


    def add_indicators(self, df):

        # Tendencias
        df["EMA_50"] = ta.trend.ema_indicator(
            df["close"],
            window=50
        )

        df["EMA_200"] = ta.trend.ema_indicator(
            df["close"],
            window=200
        )


        # Fuerza del movimiento
        df["RSI"] = ta.momentum.rsi(
            df["close"],
            window=14
        )


        # Volatilidad
        df["ATR"] = ta.volatility.average_true_range(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14
        )


        return df