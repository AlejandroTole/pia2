# PIA Decisions Log

## Decisión 001

Fecha:
Julio 2026

Tema:
Modelo de IA local

Decisión:

Usar Ollama como infraestructura local.

---

## Decisión 002

Tema:
Arquitectura

Decisión:

Usar arquitectura multi-agente.

---

## Decisión 003

Tema:
Memoria

Decisión:

Separar memoria del modelo de IA.

La memoria pertenece a PIA, no al LLM.

---

## Decisión 004

Tema:
Base de datos

Decisión:

Usar SQLite inicialmente.

Preparar arquitectura para migrar a vector database.

---

## Decisión 005

Fecha:
2026-07-23

Tema:
Sizing de riesgo

Decisión:

Reemplazar el tope por nocional por un tope de margen estimado por trade.

Motivo:

El tope por nocional bloqueaba operaciones FX válidas con lotes bajos.

Resultado esperado:

Controlar exposición efectiva de cuenta sin descartar señales útiles por tamaño nominal.

---

## Decisión 006

Fecha:
2026-07-23

Tema:
Anti-reentrada en símbolo

Decisión:

Agregar bloqueo de stacking por símbolo y cooldown post pérdida por símbolo+dirección.

Motivo:

Reducir pérdidas por entradas consecutivas en el mismo activo tras señal fallida.

Resultado esperado:

Menor concentración de riesgo intradía y menor probabilidad de doble SL consecutivo.

---

## Decisión 007

Fecha:
2026-07-23

Tema:
Conteo de posiciones para guard de riesgo

Decisión:

Usar conteo global de posiciones abiertas en el gate de max_open_positions.

Motivo:

El conteo por símbolo permitía exposición agregada no deseada.

Resultado esperado:

Cumplimiento coherente del límite de posiciones simultáneas a nivel cuenta.
