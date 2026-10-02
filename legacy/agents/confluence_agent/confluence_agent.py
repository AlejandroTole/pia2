from config import settings


class ConfluenceAgent:
    """
    Combina dos evaluaciones independientes de la misma señal:

    - DecisionEngine: su propio score normalizado (0-100), que ya incluye
      IA + histórico + tendencia técnica + momentum + memoria.
    - ConfluenceAgent (este mismo): su propio score normalizado (0-100),
      basado en IA + histórico + multi-timeframe + memoria.

    Antes, ConfluenceAgent sumaba el score crudo de DecisionEngine dentro
    de su propia suma de puntos → esto contaba dos veces la confianza de
    la IA, el histórico y la memoria (ambos agentes puntuaban lo mismo
    por separado). Ahora se combinan como un ensemble ponderado explícito:

        final_score = DECISION_WEIGHT * decision_score
                    + CONFLUENCE_WEIGHT * confluence_score

    Los pesos viven en settings.py (DECISION_ENGINE_WEIGHT) para que sean
    ajustables (candidatos naturales para ai_brain/learning_agent).
    """

    def __init__(self):
        print("🔗 Confluence Agent iniciado")

        self.min_score = settings.CONFLUENCE_MIN_SCORE

        # Peso de DecisionEngine en la combinación final. El resto
        # (1 - decision_weight) es el peso de este mismo agente.
        # Requiere agregar a settings.py:
        #     DECISION_ENGINE_WEIGHT = 0.4
        self.decision_weight = settings.DECISION_ENGINE_WEIGHT
        self.confluence_weight = 1.0 - self.decision_weight

    def evaluate(
            self,
            trading_signal,
            decision_data=None,
            historical_data=None,
            timeframe_data=None,
            memory_data=None
    ):

        # Compatibilidad con llamadas legacy del estilo:
        # agent.evaluate(trading_signal, historical_data, timeframe_data, memory_data)
        if historical_data is None and timeframe_data is None and memory_data is None:
            if isinstance(decision_data, dict) and "bias" in decision_data:
                historical_data = decision_data
                timeframe_data = {}
                memory_data = {}
                decision_data = {"signal": trading_signal.get("signal", "WAIT"), "score": trading_signal.get("confidence", 0)}
        elif (
            isinstance(decision_data, dict)
            and "bias" in decision_data
            and isinstance(historical_data, dict)
            and "direction" in historical_data
        ):
            # legacy order detected: (signal, historical, timeframe, memory)
            memory_data = timeframe_data
            timeframe_data = historical_data
            historical_data = decision_data
            decision_data = {"signal": trading_signal.get("signal", "WAIT"), "score": trading_signal.get("confidence", 0)}

        if decision_data is None:
            decision_data = {"signal": trading_signal.get("signal", "WAIT"), "score": trading_signal.get("confidence", 0)}
        if historical_data is None:
            historical_data = {}
        if timeframe_data is None:
            timeframe_data = {}
        if memory_data is None:
            memory_data = {}

        ai_signal = trading_signal.get("signal", "WAIT")
        ai_confidence = trading_signal.get("confidence", 0)

        # La señal de trabajo es la de DecisionEngine (que ya incluye la
        # recuperación histórica cuando la IA dice WAIT). Si por algún
        # motivo no viene, usamos la señal cruda de la IA como respaldo.
        working_signal = decision_data.get("signal", ai_signal)

        if working_signal == "WAIT":
            return {
                "approved": False,
                "signal": "WAIT",
                "original_signal": ai_signal,
                "final_score": 0,
                "decision_component": decision_data.get("score", 0),
                "confluence_component": 0,
                "ai_confidence": ai_confidence,
                "confidence": 0,
                "reasons": ["Sin señal de trabajo (IA y Decision Engine coinciden en WAIT)"],
            }

        # ==================================
        # SCORE PROPIO DE CONFLUENCE (sin decision_score sumado adentro)
        # ==================================
        score = 0
        reasons = []

        # IA CONFIDENCE
        if ai_confidence >= 80:
            score += 30
            reasons.append("IA con alta confianza")
        elif ai_confidence >= 65:
            score += 20
            reasons.append("IA con confianza aceptable")
        else:
            score -= 10
            reasons.append("IA baja confianza")

        # HISTORICAL INTELLIGENCE
        historical_bias = historical_data.get("bias", "NONE")
        historical_confidence = historical_data.get("confidence", 0)

        if historical_bias == working_signal:
            if historical_confidence >= 10:
                score += 20
                reasons.append("Histórico confirma dirección")
            else:
                reasons.append("Histórico confirma pero con baja confianza")
        elif historical_bias != "NONE":
            score -= 10
            reasons.append("Histórico contradice")

        # TIMEFRAME
        # timeframe_score (0-100) mide la MAGNITUD de la tendencia multi-
        # timeframe, no si confirma o contradice — eso lo indica
        # timeframe_direction por separado. Se combinan: el bono/penalización
        # se escala según qué tan fuerte es esa tendencia.
        timeframe_direction = timeframe_data.get("direction", "NEUTRAL")
        timeframe_score = timeframe_data.get("score", 0)
        alignment = timeframe_data.get("alignment", False)
        strength_ratio = max(0, min(100, timeframe_score)) / 100.0

        if timeframe_direction == working_signal:
            contribution = round(20 * strength_ratio, 1)
            score += contribution
            reasons.append(f"Multi timeframe confirma (fuerza {timeframe_score}/100, +{contribution})")
        elif timeframe_direction == "NEUTRAL":
            reasons.append("Multi timeframe sin tendencia clara")
        else:
            contribution = round(10 * strength_ratio, 1)
            score -= contribution
            reasons.append(f"Timeframe contradice (fuerza {timeframe_score}/100, -{contribution})")

        if alignment:
            score += 10
            reasons.append("Alta alineación temporal")

        # MEMORY
        win_rate = memory_data.get("win_rate", 0)

        if win_rate >= 60:
            score += 15
            reasons.append("Memoria rentable")
        elif 0 < win_rate < 40:
            score -= 10
            reasons.append("Memoria con bajo rendimiento")

        confluence_normalized = max(0, min(100, score))

        # ==================================
        # COMBINACIÓN PONDERADA (ensemble)
        # ==================================
        decision_normalized = decision_data.get("score", 0)  # ya viene 0-100

        final_score = (
            self.decision_weight * decision_normalized
            + self.confluence_weight * confluence_normalized
        )

        approved = final_score >= self.min_score
        final_signal = working_signal if approved else "WAIT"

        if not approved:
            reasons.append(
                f"Score final insuficiente ({final_score:.1f} < {self.min_score})"
            )

        return {
            "approved": approved,
            "signal": final_signal,
            "original_signal": ai_signal,
            "final_score": round(final_score, 1),
            "decision_component": decision_normalized,
            "confluence_component": confluence_normalized,
            "ai_confidence": ai_confidence,
            "confidence": round(final_score, 1),  # compatibilidad con código que espera "confidence"
            "timeframe_score": timeframe_score,
            "historical_bias": historical_bias,
            "historical_confidence": historical_confidence,
            "memory_win_rate": win_rate,
            "reasons": reasons,
        }