from memory.memory_manager import MemoryManager



print("==============================")

print("     TEST MEMORY MANAGER")

print("==============================")



memory = MemoryManager()



test_data = {


    "symbol": "GBPUSD.PRO",


    "signal": "BUY",


    "confidence": 65,


    "risk": 0.5


}



memory.save(test_data)



print("\n✅ Datos guardados")


print("\nContenido de memoria:")


print(

    memory.get_all()

)