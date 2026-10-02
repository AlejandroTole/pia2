from agents.historical_agent.feature_search import HistoricalFeatureSearch


agent = HistoricalFeatureSearch()


market = {

    "rsi":38,

    "atr":0.0009,

    "trend":"Bajista",

    "momentum":"Débil",

    "volatility":"Alta"

}



result = agent.analyze(
    market
)


print("\n===== HISTORICAL INTELLIGENCE =====")

print(result)