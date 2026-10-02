"""Ensamblado de la aplicación PIA 2.0 (factory).
 
Construye y conecta todos los componentes a partir de la configuración. Se
separa de main.py para poder testear el ensamblado y reutilizarlo.
"""
 
from __future__ import annotations
 
import os
 
from pia2.ai.analyst import TradingAnalyst
from pia2.ai.llm_client import OllamaClient
from pia2.brokers.base import BrokerInterface
from config.schema import PIAConfig
from pia2.core.engine import TradingEngine
from pia2.core.orchestrator import Orchestrator
from pia2.memory.store import TradeStore
from pia2.notify.base import ConsoleNotifier, Notifier
from pia2.risk.risk_guard import RiskGuard
 
 
def build_mt5_broker(config: PIAConfig) -> BrokerInterface:
    from pia2.brokers.mt5_broker import MT5Broker
 
    login = os.environ.get("MT5_LOGIN")
    return MT5Broker(
        login=int(login) if login else None,
        password=os.environ.get("MT5_PASSWORD") or None,
        server=os.environ.get("MT5_SERVER") or None,
        account_type_required=config.account_type_required,
        symbols=config.broker_symbols(),
        default_deviation=config.deviation,
    )
 
 
def build_orchestrator(
    config: PIAConfig,
    broker: BrokerInterface,
    notifier: Notifier | None = None,
    db_path: str = "data/runtime/pia.db",
) -> Orchestrator:
    notifier = notifier or ConsoleNotifier()
    if db_path == "data/runtime/pia.db":
        login = os.environ.get("MT5_LOGIN", "unknown")
        db_path = f"data/runtime/pia_{config.account_type_required}_{login}.db"
    store = TradeStore(db_path)
    guard = RiskGuard(config.risk, store=store, timezone_name=config.schedule.timezone)
 
    base_url = config.ai.base_url
    if config.ai.port:
        base_url = base_url.rsplit(":", 1)[0] + f":{config.ai.port}"

    client = OllamaClient(
        model=config.ai.model,
        base_url=base_url,
        timeout=config.ai.timeout_seconds,
    )
    analyst = TradingAnalyst(client)
 
    engine = TradingEngine(
        config=config,
        broker=broker,
        analyst=analyst,
        store=store,
        guard=guard,
        notifier=notifier,
    )
    return Orchestrator(config, broker, engine, store, guard, notifier)