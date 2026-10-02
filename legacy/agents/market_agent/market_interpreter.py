class MarketInterpreter:


    def analyze(self, data):

        price = data["price"]
        ema50 = data["ema50"]
        ema200 = data["ema200"]
        rsi = data["rsi"]
        atr = data["atr"]


        # Tendencia

        if ema50 > ema200:
            trend = "Alcista"
        else:
            trend = "Bajista"


        # Momentum

        if rsi > 70:
            momentum = "Sobrecompra"

        elif rsi < 30:
            momentum = "Sobreventa"

        elif rsi > 50:
            momentum = "Positivo"

        else:
            momentum = "Débil"


        # Volatilidad

        if atr > 0.0005:
            volatility = "Alta"

        else:
            volatility = "Moderada"


        report = {

            "tendencia": trend,

            "momentum": momentum,

            "volatilidad": volatility,

            "precio": price

        }


        return report