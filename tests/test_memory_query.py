from memory.memory_manager import MemoryManager

print("==============================")
print("     TEST MEMORY QUERY")
print("==============================")


memory = MemoryManager()


print("\n📌 Todas las señales:")
print(
    memory.get_all()
)


print("\n📌 GBPUSD.PRO:")
print(
    memory.search_symbol(
        "GBPUSD.PRO"
    )
)


print("\n📌 BUY:")
print(
    memory.search_signal(
        "BUY"
    )
)


print("\n📌 Confianza mayor a 60:")
print(
    memory.search_confidence(
        60
    )
)


print("\n📌 Últimas señales:")
print(
    memory.recent(5)
)


print("\n📊 Estadísticas:")
print(
    memory.statistics()
)