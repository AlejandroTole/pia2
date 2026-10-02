import MetaTrader5 as mt5

from pia2.agents.historical_agent.multi_historical_builder import MultiHistoricalBuilder


SYMBOLS = [
    "EURUSD.PRO",
    "GBPUSD.PRO",
    "USDCAD.PRO",
    "USDJPY.PRO",
    "XAUUSD.PRO",
]


if __name__ == "__main__":
    if not mt5.initialize():
        print("❌ Error conectando MetaTrader 5")
        quit()

    print("✅ MetaTrader 5 conectado correctamente")

    builder = MultiHistoricalBuilder()
    builder.build_all(SYMBOLS)

    mt5.shutdown()
    print("\n✅ Histórico regenerado y MT5 cerrado")