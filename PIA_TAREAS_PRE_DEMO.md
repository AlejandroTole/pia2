# PIA 2.0 — Tareas previas a la prueba en cuenta demo

Instrucciones para el asistente de IA:

1. Lee primero CLAUDE.md, CURRENT_STATE.md, TODO.md, ARCHITECTURE.md y DECISIONS.md.
2. Trabaja UNA fase a la vez. Al terminar una fase, ejecuta los tests, resume los cambios y espera confirmación antes de seguir.
3. No elimines funcionalidades. Lo que quede sin uso se mueve a `legacy/`, no se borra.
4. Cada corrección de bug debe llevar un test que falle antes y pase después.
5. Al terminar cada fase, actualiza CURRENT_STATE.md, TODO.md y CHANGELOG.md.
6. Si algo depende del terminal MT5 real y no se puede probar sin él, márcalo "VERIFICAR EN MT5" y no lo des por resuelto.
7. Nunca cambies `config.yaml` a un modo que envíe órdenes a una cuenta live.

Antes de empezar: haz un commit de git (o copia la carpeta completa) para poder revertir.

---

## FASE 0 — Seguridad

- [x] **P0-1** Al conectar, verificar `account_info().trade_mode == ACCOUNT_TRADE_MODE_DEMO`. Añadir `require_demo_account: true` al config y abortar si la cuenta no es demo. Imprimir login y servidor. Verificar `terminal_info().trade_allowed` y `account_info().trade_allowed`.
- [x] **P0-2** Reemplazar `mode: demo|real` por dos ejes: `execution: simulated | broker` y `account_type_required: demo | live`. Dejar `config.example.yaml` con valores seguros.
- [x] **P0-3** Mover `.env` a la raíz del proyecto (hoy está en `pia2/pia2/` y `main.py` no lo carga). Poner un `.gitignore` en la raíz que cubra `.env`, `config/config.yaml`, `*.db`, `logs/`, `.venv/`.
- [x] **P0-4** Kill switch: si existe el archivo `STOP` en la raíz, el loop no abre operaciones nuevas. Opcional: comando para cerrar todas las posiciones con magic 999999.
- [x] **P0-5** Base de datos separada por cuenta (`pia_demo_<login>.db`) o columna `account_login`. Archivar la `pia.db` actual sin borrarla.

**Aceptación:** con una cuenta live conectada el bot se niega a arrancar; con la demo arranca e imprime login/servidor.

## FASE 1 — Bugs que invalidan la prueba

- [x] **P1-1** Operar solo con velas cerradas: `copy_rates_from_pos(symbol, tf, 1, count)` (o descartar la última fila). Aplicar lo mismo en `multi_historical_builder`.
- [x] **P1-2** Backtest (`historical_backtest.py`):
  - Añadir una barra al `PatternRuntimeIndex` solo cuando ya pasaron sus 4 barras de horizonte (hoy hay lookahead).
  - Simular SL/TP con high/low de las velas siguientes; si ambos caben en la misma vela, asumir SL primero.
  - Incluir spread, comisión y deslizamiento configurables.
  - Añadir separación walk-forward (entrenamiento / prueba).
- [x] **P1-3** Conciliación (`reconciler.py`, `mt5_broker.py`):
  - Consultar historial con `to = ahora + 1 día` y manejar UTC vs hora del servidor. VERIFICAR EN MT5.
  - `closed_at` = hora real del deal, no la de detección.
  - Sumar comisión, swap y fee al P/L.
  - No aplicar al día actual pérdidas de días anteriores: usar la fecha del deal.
  - Cruzar trades PENDING con `positions_get()`; si el ticket ya no existe, buscar deals con `history_deals_get(position=ticket)`; si no aparece, marcar `UNKNOWN`.
- [x] **P1-4** `reconciler.py` no importa `pandas` (`pd` da NameError en `_find_exit`). Importarlo. `_reconcile_demo` debe procesar solo trades simulados (no los reales). Las posiciones simuladas deben contar para los límites del guard.
- [x] **P1-5** RiskGuard con estado persistente: trades del día, P/L del día, pico de equity y balance de inicio de día se reconstruyen al reiniciar (desde la base y el broker). Calcular la pérdida diaria con equity (incluye flotante). Definir el "día" en la zona horaria de `schedule.timezone`, no en UTC.
- [x] **P1-6** Guardia de margen: usar `mt5.order_calc_margin()` en lugar de `volume * contract_size / leverage`. Revisar también `margin_free` y `margin_level`.
- [x] **P1-7** `normalize_volume` debe redondear hacia abajo. Si al aplicar `volume_min` el riesgo real supera ~1.25× el objetivo, rechazar la operación. Guardar el riesgo real en dinero.
- [x] **P1-8** `ai/analyst.py`: eliminar `_parse_freeform` como fuente de señales (si el JSON falla → WAIT). En `llm_client.py`, construir el JSON de error con `json.dumps` para no generar JSON inválido.
- [x] **P1-9** Alinear `max_open_positions` entre `config.yaml` (1) y la documentación (1). Para la demo empezar con 1 o 2. Añadir un límite de exposición por divisa (p. ej. no más de N posiciones con USD en el mismo sentido).

**Aceptación:** tests focalizados pasan (40); una simulación con posiciones PENDING mezcladas no lanza NameError; el backtest ya no usa datos futuros. VERIFICAR EN MT5 los puntos dependientes del terminal real.

## FASE 2 — Ejecución en MT5

- [ ] `type_filling`: leer de `symbol_info.filling_mode` en lugar de fijar IOC. VERIFICAR EN MT5.
- [ ] Llamar `symbol_select(symbol, True)` para los 5 símbolos al arrancar y validar `trade_mode`, `stops_level` y `freeze_level`.
- [ ] Usar `order_check()` antes de `order_send()`; reintentar solo requote/off quotes.
- [ ] Recalcular SL/TP sobre el precio real de entrada justo antes de enviar; rechazar si el precio se movió más de X·ATR desde el análisis. Tras abrir, confirmar que SL/TP quedaron en la posición.
- [ ] `deviation` configurable en el YAML.
- [ ] `max_spread_points` por símbolo (diccionario en el config).
- [ ] Ollama: timeout menor, presupuesto de tiempo por ciclo, `keep_alive`, `num_ctx` fijo, temperatura 0 con seed. Alinear o eliminar el `Modelfile` (apunta a qwen3.6, el config usa qwen2.5:7b).
- [ ] Decidir el horizonte: cierre forzado al final de sesión y antes del fin de semana, o aceptar swap y gaps (documentarlo en DECISIONS.md).

## FASE 3 — Datos, noticias e IA

- [ ] Noticias: `news.db` solo tiene FXStreet; 0 eventos del calendario de Forex Factory. Sustituir el scraping por regex por una fuente estructurada, o añadir una lista manual de bloqueos en el config. Verificar la zona horaria de la hora del evento. Avisar en el log si no hay eventos futuros cargados. Proteger posiciones abiertas antes de eventos de alto impacto.
- [ ] Features históricas: usar los mismos indicadores en el constructor y en vivo (`ta`: RSI de Wilder, ATR con true range, EMA igual). Arreglar el import `pia2.config.settings` en `multi_historical_builder.py`. Leer los parámetros de la sección `historical:` del YAML (hoy se leen de `config/settings.py`). Regenerar los JSON.
- [ ] Añadir una regla determinista de referencia (tendencia EMA + RSI + patrón, mismo SL/TP) para comparar contra el LLM.

## FASE 4 — Observabilidad

- [ ] Tabla `signals`: registrar TODAS las evaluaciones (hora, símbolo, features, respuesta cruda del LLM, decisión, filtro que bloqueó, latencia).
- [ ] Tablas `orders` (precio pedido vs ejecutado, deslizamiento, spread, retcode) y `account_snapshots` (balance, equity, margen).
- [ ] Guardar comisión, swap, MAE/MFE y hora real de cierre en `trades`.
- [ ] Logging a archivo con rotación; notificador de Telegram (el `.env` ya lo prevé).
- [ ] Script de reporte diario: profit factor, expectancy en R, aciertos por símbolo y sesión, drawdown, deslizamiento medio, órdenes rechazadas.
- [ ] Chequeo de salud de MT5 (`terminal_info().connected`) y de Ollama; reinicio automático.
- [ ] UTC de punta a punta; reemplazar `datetime.utcnow()` (deprecado).
- [ ] Loader de config estricto: error o warning ante claves desconocidas.

## FASE 5 — Orden del proyecto y tests

- [ ] Resolver la estructura `pia2/pia2/` anidada con `config/` fuera del paquete; rutas relativas a la raíz del proyecto (no al directorio actual). Fijar una versión de Python y borrar los `.pyc` mezclados.
- [ ] Mover a `legacy/` lo no conectado al flujo real: `ConfluenceAgent`, `MarketAgent`, `TradeSetupAgent`, `intelligence/`, `execution/trade_executor.py`, `memory_manager`. Actualizar ARCHITECTURE.md para reflejar lo que realmente corre.
- [ ] Crear `pia2/brokers/paper_broker.py` (broker simulado que implemente `BrokerInterface`) y arreglar `test_engine_flow.py`.
- [ ] Arreglar o retirar los tests rotos: `test_feature_builder`, `test_historical_analysis`, `test_learning`, `test_memory_agent`, `test_memory_query`.
- [ ] Tests nuevos: cierre de vela, conciliación, persistencia del guard, chequeo de cuenta demo, parser del LLM, sizing (redondeo hacia abajo).

## Protocolo de prueba (después de las fases 0–2 como mínimo)

1. **Humo (1–2 días):** 1–2 símbolos, lote mínimo, `max_open_positions: 1`. Comprobar: órdenes con SL/TP, cierre manual reflejado en < 1 minuto con hora real, reinicio con posición abierta restaura el estado, Ollama apagado → WAIT, MT5 desconectado → reconecta.
2. **Prueba (≥ 4 semanas y ≥ 100 operaciones cerradas):** 5 símbolos, riesgo 0.25–0.5%, registrando todas las señales y comparando con la regla de referencia.
3. **Criterios de paso (netos de costos):** profit factor > 1.2, drawdown dentro del límite, conciliación 100% contra el historial de MT5, cero violaciones de guardas, cero excepciones sin manejar.