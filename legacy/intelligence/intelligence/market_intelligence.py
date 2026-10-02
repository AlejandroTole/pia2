class MarketIntelligence:


    def __init__(self):

        print("🧠 Market Intelligence iniciado")



    def evaluate(
            self,
            market_data,
            trading_signal,
            memory_context
    ):


        score = 0

        reasons = []



        # ==================================
        # DATOS BASE
        # ==================================

        signal = trading_signal.get(
            "signal",
            "WAIT"
        )



        confidence = trading_signal.get(
            "confidence",
            0
        )



        # ==================================
        # SI IA DICE WAIT
        # NO TERMINAMOS
        # ==================================

        if signal == "WAIT":

            reasons.append(
                "IA indecisa, evaluando condiciones técnicas"
            )


            # Intentamos detectar dirección probable

            rsi = market_data.get(
                "rsi",
                50
            )


            trend = market_data.get(
                "trend",
                ""
            )


            momentum = market_data.get(
                "momentum",
                ""
            )



            if rsi < 40:

                score += 15

                reasons.append(
                    "RSI en zona de recuperación"
                )



            if trend == "Alcista":

                score += 20

                reasons.append(
                    "Tendencia alcista"
                )


            elif trend == "Bajista":

                score -= 15

                reasons.append(
                    "Tendencia bajista"
                )



            if momentum == "Positivo":

                score += 15

                reasons.append(
                    "Momentum positivo"
                )


            elif momentum == "Débil":

                score -= 10

                reasons.append(
                    "Momentum débil"
                )



            signal = self.detect_direction(
                market_data
            )



        else:


            # ==================================
            # ANALISIS NORMAL BUY / SELL
            # ==================================

            trend = market_data.get(
                "trend",
                ""
            )


            momentum = market_data.get(
                "momentum",
                ""
            )


            rsi = market_data.get(
                "rsi",
                50
            )



            if signal == "BUY":


                if trend == "Alcista":

                    score += 30

                    reasons.append(
                        "Compra alineada con tendencia"
                    )


                else:

                    score -= 20

                    reasons.append(
                        "Compra contra tendencia"
                    )



                if momentum == "Positivo":

                    score += 15

                    reasons.append(
                        "Momentum favorece compra"
                    )



                if rsi < 40:

                    score += 15

                    reasons.append(
                        "RSI favorece recuperación"
                    )




            elif signal == "SELL":


                if trend == "Bajista":

                    score += 30

                    reasons.append(
                        "Venta alineada con tendencia"
                    )


                else:

                    score -= 20

                    reasons.append(
                        "Venta contra tendencia"
                    )



        # ==================================
        # VOLATILIDAD
        # ==================================

        volatility = market_data.get(
            "volatility",
            ""
        )


        if volatility == "Alta":

            score -= 10

            reasons.append(
                "Volatilidad elevada"
            )


        elif volatility == "Moderada":

            score += 10

            reasons.append(
                "Volatilidad estable"
            )




        # ==================================
        # MEMORIA
        # ==================================

        win_rate = memory_context.get(
            "win_rate",
            0
        )


        previous_cases = memory_context.get(
            "previous_cases",
            0
        )



        if previous_cases > 0:


            if win_rate >= 60:

                score += 15

                reasons.append(
                    "Historial rentable"
                )


            elif win_rate < 40:

                score -= 10

                reasons.append(
                    "Historial negativo"
                )



        # ==================================
        # CONFIANZA IA
        # ==================================

        if confidence >= 80:

            score += 10

            reasons.append(
                "Alta confianza IA"
            )



        # ==================================
        # RESULTADO
        # ==================================

        approved = False


        if score >= 40:

            approved = True



        return {


            "approved": approved,

            "score": score,

            "signal": signal,

            "reasons": reasons

        }



    # ==================================
    # DETECTAR DIRECCION CUANDO IA ESPERA
    # ==================================

    def detect_direction(
            self,
            market_data
    ):


        rsi = market_data.get(
            "rsi",
            50
        )


        trend = market_data.get(
            "trend",
            ""
        )


        momentum = market_data.get(
            "momentum",
            ""
        )



        if rsi < 35 and momentum != "Débil":

            return "BUY"



        if trend == "Bajista" and rsi > 60:

            return "SELL"



        return "WAIT"