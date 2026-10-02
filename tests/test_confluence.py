from agents.confluence_agent.confluence_agent import ConfluenceAgent


print("==============================")
print("   CONFLUENCE TEST")
print("==============================")


agent = ConfluenceAgent()



trading_signal = {

    "signal": "BUY",

    "confidence": 85

}



historical_data = {

    "bias": "BUY",

    "confidence": 35

}



timeframe_data = {

    "direction": "BUY",

    "alignment": True,

    "score": 90

}



memory_data = {

    "win_rate": 70

}



result = agent.evaluate(

    trading_signal,

    historical_data,

    timeframe_data,

    memory_data

)



print("\nRESULTADO:")
print(result)