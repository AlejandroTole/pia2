from agents.historical_agent.feature_builder import HistoricalFeatureBuilder


builder = HistoricalFeatureBuilder()


result = builder.build()


print("\n===== FEATURE TEST =====")

print(result[0])