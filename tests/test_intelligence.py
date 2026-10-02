from intelligence.market_intelligence import MarketIntelligence



engine = MarketIntelligence()



market_data = {


    "trend": "Bajista",

    "momentum": "Positivo",

    "volatility": "Alta",

    "rsi": 52


}



trading_signal = {


    "signal": "BUY",

    "confidence": 85


}



memory_context = {


    "previous_cases": 4,

    "average_previous_confidence": 75


}



result = engine.evaluate(

    market_data,

    trading_signal,

    memory_context

)



print("\n===== MARKET INTELLIGENCE TEST =====")

print(result)