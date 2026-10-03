# PIA TODO

## Fases pre-demo

- [x] FASE 0: seguridad de cuenta, `.env`, kill switch y base separada por cuenta.
- [x] FASE 1: corregir bugs que invalidan la prueba.
- [x] FASE 2: validación de ejecución MT5 en regresión (`symbol_select`, metadata del símbolo, `order_check`, `deviation` y `filling_mode`).
  - VERIFICAR EN MT5: validación final con cuenta real, permisos del terminal y respuesta real del broker.
- [x] Corregir validación de metadata MT5 para usar `trade_stops_level` y `trade_freeze_level`; regresión focalizada 2/2 y conexión verificada con cuenta demo.
- [x] Aplicar `pia2-fixes.patch`: README, instalación editable, imports, filling mode, failover de noticias y paridad del backtest; `pytest tests -q` pasó.
- [x] FASE 3: compatibilidad de imports históricos, `config.settings` sin MT5, uso de indicadores del YAML en `MultiHistoricalBuilder`, regla determinista de referencia basada en EMA + RSI + patrón de velas y soporte de eventos manuales estructurados para noticias con timezone UTC-aware.
  - Validación focalizada: 5 tests pasados (builder histórico + compatibilidad + referencia + noticias + config).
  - VERIFICAR EN MT5: descarga/regen del histórico real y validación del calendario de noticias con el terminal real.
  - Bloqueador heredado: suite de flujo más amplia sigue necesitando `pia2.brokers.paper_broker` (FASE 5), no por la lógica de la regla determinista.
- [x] FASE 4: observabilidad persistente con SQLite, registros de señales / órdenes / snapshots, logger rotativo de archivos y aviso de claves desconocidas en YAML para evitar pérdida silenciosa de configuración.
  - Validación focalizada: 3 pruebas de observabilidad + carga de config (nueva regresión de `unknown` keys) pasan en conjunto.
  - Notificador de Telegram añadido con `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`; si faltan variables, no rompe el entorno demo.
- [x] FASE 5 (bloqueador inicial): creación de `pia2.brokers.paper_broker` y compatibilidad del import legacy `tests.test_analyst` para la suite de flujo.
  - Validación focalizada: `test_engine_flow.py` pasa en 4/4 casos.
  - Queda pendiente la limpieza estructural `legacy/` y la revisión del resto del conjunto de pruebas rotas según la hoja de ruta.
- [x] Compatibilidad legacy final: restauración de los imports `agents.*` y la API legacy de `MemoryManager` / `ConfluenceAgent` para que el entorno no rompa la colección del proyecto en ausencia de MT5 real.
  - Verificación realizada con un script de regresión que importó y ejecutó las interfaces heredadas y devolvió `compatibility checks passed`.

Nota: la suite completa aún requiere resolver imports legacy y crear `PaperBroker`.
La batería focalizada de FASE 1 pasa: 40 tests.
La batería focalizada de FASE 2 pasa: 2 tests de regresión MT5.
La batería focalizada de FASE 3 pasa: 5 tests focalizados.
La batería focalizada de FASE 4 pasa: observabilidad + carga de config + regresión de unknown keys.
La batería focalizada de FASE 5 pasa: test_engine_flow.py (4/4).
La capa legacy de compatibilidad queda verificada con comprobaciones de import y API ejecutadas en el intérprete del proyecto.

---

# Prioridad Alta

## Memoria

- Crear memoria de corto plazo.
- Crear memoria largo plazo.
- Crear memoria semántica.
- Crear sistema de recuperación inteligente.

## Agentes

- Crear Reflection Agent.
- Crear Planner Agent.
- Mejorar AI Brain.

---

# Prioridad Media

- Sistema de backtesting.
- Gestión avanzada de riesgo.
- Dashboard.
- Visualización de decisiones.

---

# Prioridad Baja

- Interfaz gráfica.
- Optimización.
- Mejoras visuales.

---

# Investigación

- RAG local.
- Embeddings.
- Vector database.
- Aprendizaje autónomo.
