import MetaTrader5 as mt5

from agents.timeframe_agent.timeframe_agent import TimeFrameAgent



print("==============================")
print(" TIMEFRAME TEST")
print("==============================")



if not mt5.initialize():

    print("❌ MT5 error")
    quit()



agent = TimeFrameAgent()



symbols = [

    "GBPUSD.PRO",

    "EURUSD.PRO",

    "USDJPY.PRO",

    "XAUUSD.PRO"

]



for symbol in symbols:


    print("\n==============================")

    print(symbol)


    result = agent.analyze(
        symbol
    )


    print(result)



mt5.shutdown()