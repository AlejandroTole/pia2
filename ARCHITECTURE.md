# PIA Architecture

## Vista general

PIA corre sobre un núcleo operativo determinista y un conjunto de capas de soporte. La ruta activa del flujo es:

Usuario / Config YAML
↓
TradingEngine
↓
Indicadores + noticias + memoria + IA
↓
RiskGuard + RiskManager
↓
Broker (MT5 o PaperBroker)
↓
TradeStore + ObservabilityStore

---

# Flujo principal activo

## 1. Entrada y configuración
- `config/loader.py` valida y normaliza el YAML.
- `config/schema.py` define los dataclasses operativos.

## 2. Decisión por símbolo
- `pia2/core/engine.py` orquesta el ciclo por símbolo.
- `pia2/strategy/interpreter.py` define la referencia determinista.
- `pia2/strategy/indicators.py` y `pia2/strategy/candles.py` calculan señales.

## 3. Riesgo y gobernanza
- `pia2/risk/risk_guard.py` aplica circuit breakers diarios.
- `pia2/risk/risk_manager.py` calcula tamaño y margen.

## 4. Ejecución
- `pia2/brokers/base.py` define el contrato del broker.
- `pia2/brokers/mt5_broker.py` expone la conexión real.
- `pia2/brokers/paper_broker.py` soporta pruebas y CI.

## 5. Persistencia y observabilidad
- `pia2/memory/store.py` guarda trades y estado del guard.
- `pia2/observability/store.py` guarda señales, órdenes y snapshots.
- `pia2/notify/base.py` maneja logs rotativos y notificaciones.

---

# Legacy archivada

Se movieron a `legacy/` los módulos que ya no participan en el flujo principal real:

- `agents/confluence_agent`
- `agents/market_agent`
- `agents/trade_setup_agent`
- `intelligence/`
- `execution/trade_executor.py`
- `memory/memory_manager.py`

Estas piezas siguen disponibles como shims de compatibilidad para no romper imports heredados, pero ya no forman parte del runtime activo.

---

# Principios

- Modularidad real.
- Capa de riesgo activa antes de ejecutar.
- Configuración segura y sin live por defecto.
- Compatibilidad con imports legado antes de limpiar los módulos antiguos.
- Datos persistidos para auditoría y análisis posterior.
