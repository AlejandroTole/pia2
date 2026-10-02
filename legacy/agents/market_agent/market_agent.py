import MetaTrader5 as mt5

from config import settings

from mt5.market_data import get_candles

from agents.market_agent.technical_analysis import TechnicalAnalysis
from agents.market_agent.market_interpreter import MarketInterpreter

from data.database.save_analysis import save_market_analysis

from agents.trading_agent.trading_analyst import TradingAnalyst
from agents.risk_agent.risk_manager import RiskManager
from agents.memory_agent import MemoryAgent
from agents.decision_agent.decision_engine import DecisionEngine
from agents.historical_agent.historical_intelligence import HistoricalIntelligence
from agents.timeframe_agent.timeframe_agent import TimeFrameAgent
from agents.confluence_agent.confluence_agent import ConfluenceAgent
from agents.trade_setup_agent.trade_setup_agent import TradeSetupAgent

from execution.trade_executor import TradeExecutor


class MarketAgent:

    def __init__(self):
        print("📊 Market Agent iniciado")

        self.analysis = TechnicalAnalysis()
        self.interpreter = MarketInterpreter()
        self.memory = MemoryAgent()
        self.trading = TradingAnalyst()
        self.decision = DecisionEngine()
        self.confluence = ConfluenceAgent()
        self.trade_setup = TradeSetupAgent()
        self.risk = RiskManager()
        self.historical = HistoricalIntelligence()
        self.timeframe = TimeFrameAgent()
        self.executor = TradeExecutor(memory=self.memory)

    # ==================================
    # PRECIO ACTUAL
    # ==================================

    def get_current_price(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            return tick.bid
        return None

    # ==================================
    # BALANCE REAL DE LA CUENTA
    # ==================================

    def get_account_balance(self):
        """
        Antes: RiskManager recibía un balance hardcodeado (3000). Ahora se
        trae siempre el balance real de la cuenta conectada (demo o real,
        según lo que MT5 tenga activo).
        """
        account_info = mt5.account_info()
        if account_info is None:
            print("⚠️ No se pudo obtener account_info() de MT5")
            return 0
        return account_info.balance

    # ==================================
    # ANALISIS DE MERCADO
    # ==================================

    def analyze_market(self, symbol):
        print(f"\nAnalizando {symbol}...")

        candles = get_candles(symbol, settings.TIMEFRAME, settings.CANDLES)

        if candles is None:
            return None

        candles = self.analysis.add_indicators(candles)
        return candles

    # ==================================
    # REPORTE PRINCIPAL
    # ==================================

    def report(self, symbol):
        data = self.analyze_market(symbol)

        if data is None:
            print("❌ Sin datos")
            return None

        last = data.iloc[-1]

        market_data = {
            "symbol": symbol,
            "price": float(last["close"]),
            "ema50": float(last["EMA_50"]),
            "ema200": float(last["EMA_200"]),
            "rsi": float(last["RSI"]),
            "atr": float(last["ATR"]),
        }

        interpretation = self.interpreter.analyze(market_data)

        market_data.update({
            "trend": interpretation["tendencia"],
            "momentum": interpretation["momentum"],
            "volatility": interpretation["volatilidad"],
        })

        print("\n===== MARKET DATA =====")
        print(market_data)

        # ==================================
        # HISTORICAL
        # ==================================
        historical_context = self.historical.analyze(market_data)
        print("\n===== HISTORICAL INTELLIGENCE =====")
        print(historical_context)

        # ==================================
        # TIMEFRAME
        # ==================================
        timeframe_context = self.timeframe.analyze(symbol)
        print("\n===== TIMEFRAME ANALYSIS =====")
        print(timeframe_context)

        # ==================================
        # MEMORY (lectura de contexto previo)
        # ==================================
        # Antes: se llamaba a memory.analyze() con signal="UNKNOWN", pero
        # ningún registro se guarda jamás con esa señal (TradeExecutor
        # solo guarda BUY/SELL reales) — así que esta consulta siempre
        # devolvía "sin historial", sin importar cuántos trades reales
        # tuvieras acumulados. get_context() agrega TODO el historial del
        # símbolo, sin ese filtro roto.
        memory_context = self.memory.get_context(symbol)
        print("\n===== MEMORY CONTEXT =====")
        print(memory_context)

        # ==================================
        # AI TRADING ANALYSIS
        # ==================================
        trading_response = self.trading.analyze(market_data, memory_context)
        print("\n===== TRADING ANALYST =====")
        print(trading_response)

        # ==================================
        # UPDATE MEMORY
        # ==================================
        memory_context = self.memory.analyze({
            "symbol": symbol,
            "signal": trading_response["signal"],
            "confidence": trading_response["confidence"],
        })
        print("\n===== MEMORY UPDATED =====")
        print(memory_context)

        # ==================================
        # DECISION ENGINE
        # ==================================
        decision_response = self.decision.evaluate(
            market_data,
            trading_response,
            memory_context,
            historical_context,
        )
        print("\n===== DECISION ENGINE =====")
        print(decision_response)

        # ==================================
        # CONFLUENCE (ensemble ponderado con Decision Engine)
        # ==================================
        confluence_response = self.confluence.evaluate(
            trading_response,
            decision_response,
            historical_context,
            timeframe_context,
            memory_context,
        )
        print("\n===== CONFLUENCE ANALYSIS =====")
        print(confluence_response)

        # ==================================
        # TRADE SETUP (entry/SL/TP — única fuente de verdad)
        # ==================================
        trade_setup_response = self.trade_setup.create_setup(
            market_data,
            confluence_response,
        )
        print("\n===== TRADE SETUP =====")
        print(trade_setup_response)

        # ==================================
        # RISK
        # ==================================
        account_balance = self.get_account_balance()

        risk_response = self.risk.evaluate({
            "signal": confluence_response["signal"],
            # Antes: confluence_response["confidence"] (mezclaba el score
            # de confluencia con la confianza real de la IA). Ahora se usa
            # la confianza cruda de la IA, que es lo que este umbral debe
            # medir.
            "confidence": confluence_response["ai_confidence"],
            "balance": account_balance,
            "symbol": symbol,
            "atr": market_data["atr"],
            # sl_distance ya calculado por TradeSetupAgent (fuente única
            # de verdad). Si el setup no es válido, se pasa None y
            # RiskManager cae en su fallback interno (atr * multiplicador).
            "sl_distance": trade_setup_response.get("sl_distance"),
        })
        print("\n===== RISK MANAGER =====")
        print(risk_response)

        # ==================================
        # EXECUTION
        # ==================================
        # trade_setup_response se pasa también al executor para que, en el
        # siguiente paso (cuando conectemos trade_executor.py de verdad),
        # tenga a mano entry/SL/TP calculados sin tener que recalcularlos.
        execution_response = self.executor.execute(
            symbol,
            confluence_response,
            risk_response,
            trade_setup_response,
        )
        print("\n===== EXECUTION =====")
        print(execution_response)

        # ==================================
        # SAVE ANALYSIS
        # ==================================
        save_market_analysis(
            symbol,
            market_data["price"],
            market_data["ema50"],
            market_data["ema200"],
            market_data["rsi"],
            market_data["atr"],
        )

        return {
            "market": market_data,
            "historical": historical_context,
            "timeframe": timeframe_context,
            "trade": trading_response,
            "memory": memory_context,
            "decision": decision_response,
            "confluence": confluence_response,
            "trade_setup": trade_setup_response,
            "risk": risk_response,
            "execution": execution_response,
            "account_balance": account_balance,
        }