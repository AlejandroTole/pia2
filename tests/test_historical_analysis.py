from agents.historical_agent.historical_analyzer import HistoricalAnalyzer


agent = HistoricalAnalyzer()


market = {

    "price":1.33786,

    "rsi":43

}


result = agent.analyze(
    market
)


print("\n===== HISTORICAL RESULT =====")

print(result)