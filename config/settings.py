try:
    import MetaTrader5 as mt5
except ModuleNotFoundError:  # pragma: no cover - evitar fallo en CI o entornos sin MT5
    mt5 = None


# ==========================================================
#                   CONFIGURACIÓN GENERAL
# ==========================================================

PROJECT_NAME = "PIA"

VERSION = "0.1.0"

ENVIRONMENT = "DEMO"


# ==========================================================
#                   META TRADER
# ==========================================================

SYMBOL = "GBPUSD.PRO"

TIMEFRAME = getattr(mt5, "TIMEFRAME_M15", 0)

CANDLES = 250

# Identifica las órdenes que envía PIA en MT5 (para diferenciarlas de
# operaciones manuales u otros bots en la misma cuenta)
MAGIC_NUMBER = 999999


# ==========================================================
#                   MODELO IA
# ==========================================================

AI_MODEL = "qwen2.5:7b"

OLLAMA_URL = "http://localhost:11434"


# ==========================================================
#                   RIESGO
# ==========================================================

MAX_RISK_PERCENT = 0.5

MIN_CONFIDENCE = 60

MAX_OPEN_TRADES = 1


# ==========================================================
#            CONFLUENCIA Y MOTOR DE DECISIÓN
# ==========================================================
# Umbral final (0-100) para aprobar una operación, aplicado sobre el
# score combinado de ConfluenceAgent + DecisionEngine.
CONFLUENCE_MIN_SCORE = 45

# Peso de DecisionEngine en la combinación ponderada final.
# El resto (1 - este valor) es el peso de ConfluenceAgent.
# Ej: 0.4 = 40% Decision Engine, 60% Confluence Agent.
DECISION_ENGINE_WEIGHT = 0.4


# ==========================================================
#               INDICADORES TÉCNICOS
# ==========================================================

EMA_FAST = 50

EMA_SLOW = 200

RSI_PERIOD = 14

ATR_PERIOD = 14


# ==========================================================
#                 TAKE PROFIT / STOP LOSS
# ==========================================================

ATR_STOPLOSS_MULTIPLIER = 2.0

ATR_TAKEPROFIT_MULTIPLIER = 4.0


# ==========================================================
#              INTELIGENCIA HISTÓRICA
# ==========================================================
# Mínimo de patrones históricos similares requeridos antes de confiar en
# el sesgo (bias) calculado — evita sobreconfianza con muestras chicas
# (ej. "100% de confianza" basado en 1 solo caso parecido).
MIN_HISTORICAL_PATTERNS = 15

# Tolerancia de RSI (+/-) para considerar dos escenarios "similares" al
# buscar coincidencias en el histórico.
HISTORICAL_RSI_TOLERANCE = 10

# Fracción del ATR que un movimiento futuro debe superar para contar
# como resultado BUY/SELL decisivo al construir el histórico. Velas con
# movimiento menor a este umbral se descartan (no cuentan como ninguno).
MIN_FUTURE_MOVE_ATR_RATIO = 0.3


# ==========================================================
#                    BASE DE DATOS
# ==========================================================

DATABASE_NAME = "pia.db"


# ==========================================================
#                    LOGS
# ==========================================================

SAVE_LOGS = True

LOG_LEVEL = "INFO"


# ==========================================================
#                  FUTURAS OPCIONES
# ==========================================================

ENABLE_LEARNING = True

ENABLE_BACKTEST = True

ENABLE_DASHBOARD = True

ENABLE_AUTO_TRADE = False