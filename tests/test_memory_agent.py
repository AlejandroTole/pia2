from agents.memory_agent import MemoryAgent


print("==============================")
print("     TEST MEMORY AGENT")
print("==============================")


agent = MemoryAgent()


market_situation = {

    "symbol": "GBPUSD.PRO",

    "signal": "BUY",

    "confidence": 70

}


result = agent.analyze(
    market_situation
)


print("\n🧠 Memory Analysis:")
print(result)