# PIA Changelog

---

## 2026-10-03

### Herramientas de experimentación

- El CLI de backtest acepta una confianza mínima y ruta de configuración explícitas sin modificar el YAML de producción.
- Se añadió `tools/measure_spread.py` para medir spread histórico o muestrearlo en vivo desde MT5.
- `.gitignore` excluye configuraciones `config.exp-*.yaml`.

## 2026-10-03

### Calibración de confianza del backtest

- La confianza de `build_signal_from_counts` se calcula con el z-score del split BUY/SELL y se añade el valor `z` a la razón de señal.
- Se añadieron tests de splits balanceados, edge fuerte, margen débil con muestra grande e historial insuficiente.
- El drawdown walk-forward agregado suma variaciones entre snapshots consecutivos, evitando contar equity acumulado repetidamente.

## 2026-10-03

### Backtest walk-forward y limpieza

- Se eliminó `pia2-fixes.patch`, se corrigió la raíz del CLI y se actualizó la sección de backtest del README.
- Se añadió walk-forward multifold con límites OOS y equity agregado; las salidas simuladas quedan dentro de la ventana de evaluación.
- Los tests del constructor histórico cargan la configuración de ejemplo y no dependen de `config.yaml` local.

## 2026-10-03

### Correcciones de calendario, kill switch y fecha de riesgo

- Las horas de ForexFactory se interpretan en `America/New_York` y se convierten a UTC, con timezone de origen configurable.
- El archivo `STOP` ahora apunta a la raíz del repositorio.
- RiskGuard recibe la fecha calculada en la zona horaria configurada.
- Se añadieron tests para timezone y seguridad; la suite completa pasó con `pytest tests/ -q`.

## 2026-10-02

### Corrección de conexión MT5

- `MT5Broker.connect()` ahora valida la metadata con los atributos reales `trade_stops_level` y `trade_freeze_level` de MetaTrader5.
- Se actualizó el mock de MT5 y pasaron las 2 pruebas focalizadas; conexión local verificada con cuenta demo y los cinco símbolos.

### README, empaquetado y regresiones

- Se añadió README e instalación editable del paquete; se corrigieron imports de agentes y se eligió `type_filling` desde los flags del símbolo.
- Se añadió fail-open/fail-closed configurable para noticias y controles de paridad de backtest para spread, confianza, stacking y cooldown.
- La suite completa pasó con `pytest tests -q`.

## 2026-10-01

### FASE 5 — Broker simulado y compatibilidad de flujo

- Se implementó `pia2/brokers/paper_broker.py` con el contrato mínimo de `BrokerInterface` para pruebas de flujo, incluyendo `connect`, `account`, `get_candles`, `set_spec`, `set_tick`, `open_positions`, `place_order` y `estimate_margin`.
- El `PaperBroker` admite tanto `broker.set_spec(spec)` como `broker.set_spec("EURUSD", spec)` para mantener compatibilidad con la suite heredada.
- Se añadió un shim de compatibilidad en la raíz para `tests.test_analyst`, permitiendo importar `FakeClient` sin reordenar toda la estructura del proyecto.
- La regresión de `test_engine_flow.py` quedó verificada con 4/4 casos en verde.
- Se restauró la capa de compatibilidad legacy para `agents.*` y `MemoryManager`, con soporte para `ConfluenceAgent.evaluate` y `search_signal` / `search_confidence` / `recent` para no romper la colección del proyecto en entornos sin MT5 real.
- Se validó la compatibilidad con un script end-to-end del intérprete del proyecto, que devolvió `compatibility checks passed`.
- Queda pendiente la limpieza estructural `legacy/` y la revisión del resto del lote de pruebas rotas, según la hoja de ruta de la FASE 5.

### FASE 4 — Observabilidad y control de configuración

- Se añadió `pia2/observability/store.py` con persistencia de señales, órdenes y snapshots de cuenta, listo para análisis posterior y auditoría del flujo de decisiones.
- El motor de trading registra decisiones, latencia de IA, bloqueos por noticias y snapshots de balance/equity antes de ejecutar la orden.
- Se añadió `FileRotatingNotifier` para persistir eventos en `logs/pia.log` con rotación por tamaño y copias de seguridad.
- Se incorporó `TelegramNotifier` con variables `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`; si faltan, el sistema permanece inactivo sin romper el entorno demo.
- El loader de configuración emite `UserWarning` cuando aparezcan claves desconocidas en YAML, evitando configuraciones silenciosas.
- Se añadió `pia2/observability/report.py` para resumir eventos recientes en SQLite.
- Validación focalizada de la fase: `test_observability_store` + `test_config_loader` pasan con la nueva regresión de `unknown` keys.

### FASE 3 — Compatibilidad histórica, regla determinista y noticias estructuradas

- Se corrigió la importación heredada de `agents.historical_agent.multi_historical_builder` mediante un shim de compatibilidad en la raíz del proyecto.
- El builder histórico ya no depende de `pia2.config.settings` ni de `MetaTrader5` al momento de importar; la carga de MT5 queda retrasada al uso real del downloader.
- `MultiHistoricalBuilder` ahora genera EMA, RSI y ATR con la misma configuración que el pipeline en vivo y usa `historical.min_future_move_atr_ratio` desde el YAML, evitando valores fijos y desalineados.
- Se añadió una regla determinista de referencia en `strategy/interpreter.py` que combina EMA + RSI + patrón de velas y reutiliza el mismo SL/TP basado en ATR para comparar con la decisión del LLM y reducir confianza cuando divergen.
- La capa de noticias admite `manual_events` en el YAML con datetime ISO y `timezone` válido, permitiendo bloquear eventos clave cuando los feeds web están vacíos o fallan.
- `config/settings.py` ahora falla con gracia si el entorno no tiene MT5 instalado, preservando el valor por defecto del histórico y evitando bloqueos de CI.
- Se añadieron pruebas de regresión para import del módulo histórico, carga segura de `config.settings`, uso de la configuración del YAML en el builder, la regla determinista de referencia y la gestión de eventos manuales estructurados.
- Validación focalizada completada: 5/5 pruebas de la fase pasan.
- VERIFICAR EN MT5: regeneración real del histórico con el terminal y validación de feeds/noticias con sesión real del broker.
- Bloqueador heredado: `pia2.brokers.paper_broker` aún falta para la suite de flujo de FASE 5.

### FASE 2 — Ejecución MT5 y validación de regresión

- Se corrigió la validación de `trade_mode` del símbolo para no bloquear operadores válidos cuando el broker no expone una constante explícita de `SYMBOL_TRADE_MODE_DISABLED`.
- MT5 ahora valida `symbol_select(symbol, True)` y metadata de símbolo antes de aceptar la conexión, sin romper el flujo en entornos con mocks o metadatos parciales.
- `place_order()` usa `deviation` configurable y respeta `filling_mode` del símbolo; `order_check()` sigue siendo obligatorio antes de `order_send()`.
- La suite de regresión FASE 2 queda verificada en entorno controlado: `2/2` tests pasan.
- VERIFICAR EN MT5: validación final con terminal real y cuenta demo/live, permisos del terminal y comportamiento real de `filling_mode`/ordenes.

## 2026-09-28

### FASE 1 — Integridad pre-demo

- MT5 y el constructor histórico excluyen la vela en formación.
- El backtest dejó de usar el resultado futuro de la misma fila; resuelve SL/TP con `high/low`, prioriza SL en empate y acepta spread, slippage, comisión y corte walk-forward.
- El sizing redondea volumen hacia abajo, registra el riesgo real y rechaza lotes mínimos por encima de 1.25 veces el objetivo.
- `RiskGuard` persiste estado en SQLite, restaura tras reinicio, usa la zona horaria de sesión y considera equity para pérdida diaria.
- La conciliación usa la hora real del deal, suma comisión/swap/fee y marca `UNKNOWN` los PENDING sin posición ni deal identificable.
- Las operaciones simuladas cuentan para posiciones abiertas y se añadió límite de exposición por divisa.
- El parser LLM rechaza texto libre y devuelve `WAIT` ante JSON inválido.
- Tests focalizados de la fase: 40 correctos.
- Suite completa: bloqueada por 14 errores de colección preexistentes relacionados con imports legacy y `PaperBroker`.
- VERIFICAR EN MT5: margen real, zona horaria del servidor, historial y permisos de ejecución.

### FASE 0 — Seguridad pre-demo

- Se añadieron los ejes `execution` (`simulated`/`broker`) y `account_type_required` (`demo`/`live`), manteniendo `mode` por compatibilidad.
- MT5 ahora rechaza cuentas de tipo incorrecto y conexiones sin permisos de trading en cuenta o terminal.
- La conexión verificada imprime login, servidor y tipo de cuenta.
- `.env` se carga desde la raíz y se añadió `.gitignore` en la raíz.
- Se añadió el kill switch mediante el archivo `STOP`.
- Las bases nuevas se separan por tipo de cuenta y login configurado; la base anterior se archivó sin borrarla.
- Se añadieron tests focalizados de seguridad y configuración.
- VERIFICAR EN MT5: comportamiento con una cuenta demo/live real y permisos del terminal.

## Julio 2026

Creación del sistema de documentación para Claude Code.

Creación de:

- CLAUDE.md
- CURRENT_STATE.md
- TODO.md
- ARCHITECTURE.md
- DECISIONS.md

### 2026-07-23

Cambios aplicados en gestión de riesgo y ejecución:

- Cambio del freno de tamaño por nocional a freno por margen estimado por trade.
- Nuevo campo de configuración `max_margin_per_trade_usd` y compatibilidad legada con `max_position_size_usd`.
- AccountInfo ahora expone leverage para sizing en real.
- RiskManager calcula y valida margen estimado con leverage de cuenta.
- Engine usa conteo global de posiciones abiertas para RiskGuard.
- Bloqueo de stacking por símbolo cuando existe posición abierta del mismo símbolo.
- Cooldown post pérdida por símbolo + dirección (`cooldown_minutes_after_loss`).
- Config activa ajustada a `max_open_positions: 1` y controles anti-reentrada habilitados.
- Nuevos tests y ajustes de tests existentes para validar loader, risk y TradeStore.

---

## Agosto 2026

### 2026-08-04

Cambios aplicados en la integración con Ollama y el flujo de decisiones:

- Se añadió manejo de timeouts y errores de Ollama para evitar que el ciclo falle.
- El cliente de LLM ahora intenta arrancar el servicio local de Ollama si no está disponible.
- El sistema devuelve una señal neutral de WAIT cuando la IA no responde o no está disponible.
- El motor de trading ahora registra explícitamente el motivo del WAIT en los logs.
- La configuración de IA permite fijar el puerto de Ollama (por defecto 11434) para evitar conflictos con otros servicios o agentes.
- Se incrementó el timeout de la llamada a Ollama a 180 segundos para dar margen a respuestas más lentas en entornos locales.
- Se verificó que la API local de Ollama responde correctamente en http://localhost:11434 y que el modelo qwen2.5:7b está disponible.
