import pytest

mt5 = pytest.importorskip("MetaTrader5", reason="MetaTrader5 solo disponible en Windows")

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