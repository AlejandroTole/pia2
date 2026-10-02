import MetaTrader5 as mt5

from agents.historical_agent.historical_agent import HistoricalAgent



if not mt5.initialize():

    print("Error MT5")

    quit()



agent = HistoricalAgent()



agent.build_memory(

    "GBPUSD.PRO",

    mt5.TIMEFRAME_M15,

    50000

)



mt5.shutdown()