# PIA Current State

## Fecha

Septiembre 2026

Actualizado: 2026-10-03

---

# Estado del proyecto

PIA se encuentra en fase inicial de construcción de arquitectura multi-agente.

Estado operativo reciente:

- ForexFactory interpreta sus horas en `America/New_York` y las convierte a UTC; el timezone de origen es configurable.
- El kill switch `STOP` se resuelve en la raíz del repositorio y RiskGuard recibe la fecha local de su zona horaria configurada.
- Se retiró el patch accidental del repositorio y el backtest ahora ofrece evaluación walk-forward multifold con ventanas OOS acotadas y drawdown agregado por cambios de equity.
- La confianza del backtest ahora usa significancia z-score del split BUY/SELL, calibrada a `min_confidence` y registra el z-score en el motivo de la señal.
- FASE 0 de seguridad completada para preparar la prueba demo.
- FASE 1 de integridad de prueba completada.
- FASE 2 de ejecución MT5 validada en regresión: selección de símbolos, validación de metadata y flujo de `order_check`/`order_send` con `deviation` configurado.
- La conexión MT5 real fue reparada: `MT5Broker` valida `trade_stops_level` y `trade_freeze_level` usando los nombres expuestos por MetaTrader5; conexión verificada con cuenta demo y los cinco símbolos configurados.
- Se aplicó `pia2-fixes.patch`: README e instalación editable, resolución de imports, selección de filling mode, política configurable ante fallos de noticias y paridad adicional de backtest; la suite completa pasó.
- FASE 3 quedó completada en código y pruebas focalizadas: `agents.*` resuelve el paquete real del proyecto, el builder histórico ya no falla al importar sin MT5 ni depende de `pia2.config.settings` inexistente, ahora fabrica indicadores con la configuración cargada desde YAML, la regla determinista de referencia compara la decisión del LLM con EMA + RSI + patrón de velas y la capa de noticias admite eventos manuales estructurados desde YAML con timestamps ISO y zona horaria.
- FASE 4 quedó habilitada en observabilidad: se guardan señales, órdenes y snapshots de cuenta en SQLite, el logger rota archivos en `logs/pia.log` y se añadió un notificador Telegram sin romper el modo demo cuando no hay token o chat configurados.
- La conexión MT5 verifica tipo de cuenta y permisos antes de continuar.
- VERIFICAR EN MT5: regeneración real del histórico en el terminal y validación de feeds/noticias en cuenta real y sesión real del broker.
- `config.yaml` no fue cambiado a modo live; la cuenta requerida por defecto es demo.
- Gestión de riesgo reforzada para evitar reentradas consecutivas en el mismo símbolo.
- Sizing por margen estimado (dependiente de leverage) en lugar de freno por nocional.
- VERIFICAR EN MT5: comportamiento real con cuenta demo/live, permisos del terminal, `filling_mode`, fuentes de noticias y respuestas del servidor.

---

# Componentes creados

## MetaTrader 5

Estado:
FUNCIONANDO

Conexión establecida correctamente.

---

## Market Agent

Estado:
CREADO

Responsable de obtener información del mercado.

---

## Memory Agent

Estado:
CREADO

Responsable de gestionar memoria del sistema.

---

## Memory Manager

Estado:
CREADO

Responsable de almacenamiento y recuperación.

---

## Trading Analyst

Estado:
CREADO

Responsable de análisis de mercado.

---

## AI Brain

Estado:
CREADO

Responsable de coordinación y razonamiento.

---

# Problemas actuales

- Memoria todavía básica.
- Falta memoria semántica.
- Falta aprendizaje por experiencia.
- Falta sistema de reflexión.

Riesgos operativos aún abiertos:

- Se resolvió la dependencia ausente de `paper_broker` para la suite de flujo y se restauró el import legacy `tests.test_analyst` para que el contrato del engine pueda ejecutarse sin romper la estructura del proyecto.
- Se requiere monitoreo en vivo para calibrar `cooldown_minutes_after_loss` y `max_margin_per_trade_usd`.
- Se restauró la capa de compatibilidad para imports legacy (`agents.*` y `memory.memory_manager`) y se añadió una API no destructiva para `ConfluenceAgent.evaluate` y los query helpers heredados de `MemoryManager` (`search_signal`, `search_confidence`, `recent`).
- Validación efectiva con el intérprete del proyecto: las comprobaciones de compatibilidad de import y API se ejecutaron con éxito y pasaron en entorno local sin MT5 real.
- La suite completa sigue teniendo tareas heredadas de limpieza estructural (`legacy/`, imports aún no movidos y tests rotos adicionales), pero la regresión de flujo principal ya quedó verificada y la compatibilidad de la capa legacy quedó reforzada.
- VERIFICAR EN MT5: rechazo real de cuenta live, permisos de trading y login/servidor.
- VERIFICAR EN MT5: `order_calc_margin`, zona horaria del historial, `filling_mode` y comportamiento real de `history_deals_get`.

---

# Próximo objetivo

Siguiente fase autorizable:

1. Completar FASE 4: observabilidad persistente, logger rotativo, notificación fuera de banda y validación de carga estricta del YAML.
2. Validar ejecución específica de MT5 con terminal real (VERIFICAR EN MT5).

Pendiente de arquitectura:

3. Sistema de memoria persistente.
4. Reflection Agent.
5. Planner Agent.
6. Sistema de aprendizaje continuo.

