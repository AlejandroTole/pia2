import json
import math


class HistoricalFeatureSearch:


    def __init__(self):

        print("🔎 Historical Intelligence iniciado")


        self.file = (
            "data/historical/market_history_features.json"
        )


        self.history = self.load_history()



    def load_history(self):

        try:

            with open(
                self.file,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)


        except Exception as e:

            print(
                "❌ Error cargando histórico:",
                e
            )

            return []




    # ======================================
    # DISTANCIA ENTRE PATRONES
    # ======================================

    def calculate_similarity(
            self,
            current,
            historical
    ):


        score = 0



        # RSI
        rsi_difference = abs(
            current["rsi"]
            -
            historical["RSI"]
        )


        score += (
            max(
                0,
                30 - rsi_difference
            )
        )



        # EMA / tendencia

        if (
            current["trend"]
            ==
            historical["trend"]
        ):

            score += 25



        # Momentum

        if (
            current["momentum"]
            ==
            historical["momentum"]
        ):

            score += 20



        # Volatilidad

        if (
            current["volatility"]
            ==
            historical["volatility"]
        ):

            score += 15



        # ATR aproximado

        atr_difference = abs(
            current["atr"]
            -
            historical["ATR"]
        )


        if atr_difference < 0.0005:

            score += 10



        return score





    # ======================================
    # BUSCAR PATRONES
    # ======================================

    def search(
            self,
            market_data,
            limit=100
    ):


        results = []



        for item in self.history:


            similarity = self.calculate_similarity(
                market_data,
                item
            )


            results.append(
                {
                    "similarity": similarity,
                    "result": item["future_result"],
                    "move": item["future_move"],
                    "time": item["time"]
                }
            )



        results.sort(
            key=lambda x:x["similarity"],
            reverse=True
        )



        return results[:limit]





    # ======================================
    # ANALISIS FINAL
    # ======================================

    def analyze(
            self,
            market_data
    ):


        patterns = self.search(
            market_data
        )


        buys = 0

        sells = 0


        total_move = 0



        for p in patterns:


            if p["result"] == "BUY":

                buys += 1


            elif p["result"] == "SELL":

                sells += 1


            total_move += p["move"]





        total = (
            buys +
            sells
        )


        if total == 0:

            return {

                "bias":"UNKNOWN",

                "buy_probability":0,

                "sell_probability":0,

                "patterns":0

            }




        buy_probability = round(
            buys /
            total *
            100,
            2
        )


        sell_probability = round(
            sells /
            total *
            100,
            2
        )



        if buy_probability > sell_probability:

            bias = "BUY"

        else:

            bias = "SELL"




        return {


            "bias":bias,


            "buy_probability":
                buy_probability,


            "sell_probability":
                sell_probability,


            "patterns":
                total,


            "average_move":
                round(
                    total_move / total,
                    6
                )

        }