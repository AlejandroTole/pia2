"""Punto de entrada de PIA 2.0.
 
Uso:
    python main.py
 
Lee config/config.yaml y .env, conecta a MetaTrader 5 y arranca el loop
autónomo. En modo demo no envía órdenes reales; en modo real sí (según
'mode' en config.yaml).
"""
 
from __future__ import annotations
 
import sys
from pathlib import Path
 
from pia2.app import build_mt5_broker, build_orchestrator
from config.env import load_env
from config.loader import ConfigError, load_config
 
 
def main() -> int:
    load_env(Path(__file__).resolve().parent / ".env")
 
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[ERROR de configuración] {exc}")
        return 1
 
    print("=" * 50)
    print(
        f"  PIA 2.0  |  ejecución: {config.execution.upper()} | "
        f"cuenta requerida: {config.account_type_required.upper()}"
    )
    print("=" * 50)
 
    broker = build_mt5_broker(config)
    orchestrator = build_orchestrator(config, broker)
    orchestrator.run()
    return 0
 
 
if __name__ == "__main__":
    sys.exit(main())
