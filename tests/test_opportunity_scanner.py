import pytest

mt5 = pytest.importorskip("MetaTrader5", reason="MetaTrader5 solo disponible en Windows")

from agents.opportunity_agent.opportunity_scanner import OpportunityScanner


print("==============================")
print("   OPPORTUNITY SCANNER TEST")
print("==============================")


# ---------------------------------
# CONECTAR MT5
# ---------------------------------

if not mt5.initialize():

    print("❌ No fue posible conectar MetaTrader 5")
    quit()

print("✅ MetaTrader conectado")


scanner = OpportunityScanner()


symbols = [

    "GBPUSD.PRO",

    "EURUSD.PRO",

    "USDJPY.PRO",

    "USDCAD.PRO",

    "XAUUSD.PRO"

]


results = scanner.scan(symbols)


print("\n==============================")
print("🔎 OPPORTUNITY RANKING")
print("==============================")


for i, item in enumerate(results, start=1):

    print(f"\n#{i}")

    print(item)


mt5.shutdown()

print("\nMT5 cerrado")