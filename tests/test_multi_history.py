import MetaTrader5 as mt5

from agents.historical_agent.multi_historical_builder import MultiHistoricalBuilder



if not mt5.initialize():

    print("❌ Error MT5")
    quit()



symbols = [

    "GBPUSD.PRO",

    "EURUSD.PRO",

    "USDJPY.PRO",

    "USDCAD.PRO",

    "XAUUSD.PRO"

]



builder = MultiHistoricalBuilder()


builder.build_all(
    symbols
)


mt5.shutdown()


print("\n✅ Histórico multi mercado terminado")