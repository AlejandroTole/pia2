# PIA 2.0 — Agente autónomo de day trading (MT5 + LLM local)

> **Aviso:** proyecto educativo y experimental. Opera únicamente en **cuenta demo**.
> Ningún backtest ni modelo de lenguaje garantiza rentabilidad futura. No es
> asesoría financiera.

PIA 2.0 es un bot de day trading que combina análisis técnico, noticias y un
LLM local (Ollama) como analista asesor. El flujo por símbolo y ciclo es:

```
sesión → velas MT5 → indicadores → señal técnica → analista LLM (asesor)
  → RiskGuard → cálculo de tamaño → ejecución MT5 → reconciliación de posiciones
```

El LLM **propone**, el motor de riesgo **dispone**: ninguna operación se abre
sin pasar por `RiskGuard` (límites diarios, racha de pérdidas, spread máximo)
y `RiskManager` (tamaño por riesgo fijo).

## Requisitos

- Python 3.10+
- Windows con MetaTrader 5 instalado (cuenta demo) — `brokers/mt5_broker.py`
- Ollama corriendo localmente con un modelo descargado (p. ej. `ollama pull llama3.1`)
- Para desarrollo en Linux: `brokers/paper_broker.py` permite probar sin MT5

## Instalación

```bash
git clone https://github.com/AlejandroTole/pia2
cd pia2
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e .        # instala el paquete `pia2` (la raíz del repo es el paquete)
pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml
```

Edita `config/config.yaml` con tus símbolos, horarios, riesgo y timeout del LLM.
`config.yaml` **no** se sube al repo (está en `.gitignore`); el ejemplo
documenta todas las opciones.

## Uso

```bash
python main.py            # ciclo en vivo contra MT5 (demo)
python app.py             # punto de entrada alternativo (lee config/config.yaml)
```

### Noticias: modo de fallo configurable

`news.fail_open` (default `true`):

- `true` → si la fuente de noticias falla, el ciclo sigue sin noticias
  (sesgo neutral) y el fallo queda registrado en el log y en observabilidad
  (`block_filter="news_error"`).
- `false` → si las noticias fallan, el símbolo se omite en ese ciclo
  (fail-closed: sin noticias no se opera).

### Backtest histórico

```bash
python backtesting/historical_backtest.py \
  --features-json backtesting/features_eurusd_m15.json \
  --symbol EURUSD --timeframe M15 \
  --spread-points 20 --commission-per-lot 3.5 --slippage-points 10
```

**Alcance honesto:** el backtest reutiliza la lógica real de `RiskGuard`,
`RiskManager`, `build_trade_setup`, políticas de velas y horarios, con costos
configurables. Pero **no valida el juicio del LLM** (las señales vienen de
patrones técnicos históricos, no del modelo) y **no incluye noticias
históricas**. Úsalo para validar gestión de riesgo y costos, no para concluir
que la estrategia del LLM es rentable. Los sobrevivientes del backtest pasan a
demo; en demo se revalida y se desactiva lo que se degrade.

## Tests

```bash
pytest tests/ -q
```

En Linux, los tests que requieren MetaTrader 5 se omiten (paquete oficial
solo para Windows).

## Estructura

```
agents/        agentes (histórico, confluencia, mercado, setup, ...)
ai/            analista LLM + cliente Ollama (con timeout y degradación a WAIT)
backtesting/   backtest histórico con costos y partición train/test
brokers/       MT5 (real) y paper (simulado)
core/          engine (ciclo por símbolo, sin bloqueos) + orquestador + reconciliador
news/          filtro de noticias gratuito (fail-open/fail-closed configurable)
risk/          RiskGuard (límites) + RiskManager (tamaño por riesgo)
strategy/      indicadores, intérprete técnico, construcción de setups
config/        schema de configuración + ejemplo (config.yaml es local, no se sube)
memory/        memoria persistente del agente
observability/ registro de señales y decisiones para auditoría
```

## Documentos del proyecto

- `ARCHITECTURE.md` — arquitectura del sistema
- `CURRENT_STATE.md` — estado actual
- `TODO.md` / `PIA_TAREAS_PRE_DEMO.md` — tareas pendientes
- `DECISIONS.md` — decisiones de diseño
