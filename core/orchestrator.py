"""Loop autónomo de PIA 2.0.
 
Daemon que:
  - conecta al broker y se reconecta si se cae,
  - en cada iteración: concilia operaciones cerradas (resultado real) y, si hay
    una vela nueva en el timeframe de decisión y estamos en horario, evalúa
    cada símbolo,
  - se apaga de forma segura ante Ctrl+C / SIGTERM.
 
La v1 corría una sola vez y terminaba; esto lo convierte en un agente que
opera de forma continua.
"""
 
from __future__ import annotations
 
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
 
from pia2.core.engine import TradingEngine
from pia2.core.reconciler import reconcile
from pia2.scheduling.clock import within_session
 
 
def _default_stop_file() -> Path:
    return Path(__file__).resolve().parents[1] / "STOP"


class Orchestrator:
    def __init__(self, config, broker, engine: TradingEngine, store, guard, notifier):
        self.config = config
        self.broker = broker
        self.engine = engine
        self.store = store
        self.guard = guard
        self.notifier = notifier
        self._running = False
        self._last_bar: dict[str, str] = {}
        self._last_reconcile: datetime | None = None
        self._last_heartbeat: datetime | None = None
        self._tick_seq = 0
        self._stop_file = _default_stop_file()

    def _kill_switch_active(self) -> bool:
        return self._stop_file.exists()

    def _should_log(self, level: str) -> bool:
        cfg_level = self.config.observability.log_level.upper()
        rank = {"QUIET": 0, "INFO": 1, "DEBUG": 2}
        return rank.get(cfg_level, 1) >= rank.get(level.upper(), 1)

    def _log(self, level: str, message: str) -> None:
        if self._should_log(level):
            now = datetime.now(timezone.utc).strftime("%H:%M:%S")
            self.notifier.send(f"[{now}][{level.upper()}] {message}")

    def _heartbeat(self, now: datetime) -> None:
        if self._last_heartbeat is None:
            self._last_heartbeat = now
            self._log("INFO", "heartbeat | estado=RUNNING | loop activo")
            return
        elapsed = (now - self._last_heartbeat).total_seconds()
        if elapsed >= self.config.observability.heartbeat_seconds:
            self._last_heartbeat = now
            self._log(
                "INFO",
                f"heartbeat | estado=RUNNING | tick={self._tick_seq} | poll={self.config.loop.poll_seconds}s",
            )
 
    def _install_signals(self) -> None:
        def _handler(signum, frame):
            self.notifier.send("Señal de apagado recibida, deteniendo PIA de forma segura...")
            self._running = False
 
        signal.signal(signal.SIGINT, _handler)
        try:
            signal.signal(signal.SIGTERM, _handler)
        except (ValueError, AttributeError):  # pragma: no cover - depende de plataforma
            pass
 
    def _connect_with_retry(self) -> bool:
        while self._running:
            if self.broker.is_connected() or self.broker.connect():
                self._log("INFO", "broker conectado")
                return True
            self._log(
                "INFO",
                f"No se pudo conectar al broker. Reintento en "
                f"{self.config.loop.reconnect_seconds}s..."
            )
            time.sleep(self.config.loop.reconnect_seconds)
        return False
 
    def _new_bar(self, symbol: str) -> bool:
        df = self.broker.get_candles(symbol, self.config.timeframe, 3)
        if df is None or df.empty or "time" not in df.columns:
            return False
        latest = str(df.iloc[-1]["time"])
        if self._last_bar.get(symbol) != latest:
            self._last_bar[symbol] = latest
            return True
        return False
 
    def run(self) -> None:
        self._running = True
        self._install_signals()
        self._log(
            "INFO",
            f"PIA 2.0 iniciado | modo={self.config.mode} | símbolos={self.config.symbols}"
        )
 
        if not self._connect_with_retry():
            return
 
        account = self.broker.account()
        if account is not None:
            self.guard.start_day(
                self.guard.local_date(datetime.now(timezone.utc)),
                account.balance,
            )
 
        while self._running:
            started = datetime.now(timezone.utc)
            try:
                self._tick()
            except Exception as exc:  # el loop no debe morir por un error puntual
                self.notifier.send(f"Error en el ciclo: {exc}")
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            self._log("DEBUG", f"tick_end | duration_ms={duration_ms}")
            time.sleep(self.config.loop.poll_seconds)
 
        self.broker.disconnect()
        if hasattr(self.engine, "close"):
            self.engine.close()
        self._log("INFO", "PIA 2.0 detenido.")
 
    def _tick(self) -> None:
        self._tick_seq += 1
        if not self.broker.is_connected():
            self._log("INFO", "Conexión perdida, reconectando...")
            if not self._connect_with_retry():
                return
 
        now = datetime.now(timezone.utc)
        self._heartbeat(now)
        self._log("DEBUG", f"tick_start | seq={self._tick_seq}")
 
        # 1) Conciliar resultados reales SIEMPRE (aunque estemos fuera de sesión).
        self._log("DEBUG", "reconcile_start")
        closed = reconcile(self.config, self.broker, self.store, self.guard, self._last_reconcile)
        self._last_reconcile = now
        self._log("DEBUG", f"reconcile_done | closed={closed}")
        if closed:
            stats = self.store.stats()
            self._log(
                "INFO",
                f"{closed} operación(es) cerrada(s). "
                f"Win rate: {stats['win_rate']}% | Neto: {stats['net_profit']} | "
                f"Profit factor: {stats['profit_factor']}"
            )

        if self._kill_switch_active():
            self._log("INFO", "kill_switch_active | STOP presente; no se abrirán operaciones")
            return
 
        # 2) Solo evaluar entradas dentro del horario permitido.
        if not within_session(now, self.config.schedule):
            self._log("INFO", "idle_outside_session")
            return
 
        for symbol in self.config.broker_symbols():
            if not self._new_bar(symbol):
                self._log("DEBUG", f"{symbol} | idle_waiting_new_bar")
                continue
            self._log("DEBUG", f"engine_start | symbol={symbol}")
            result = self.engine.run_symbol(symbol, now)
            action = "OPEN" if result.executed else "SKIP"
            if self.config.observability.show_symbol_summary:
                self._log(
                    "INFO",
                    f"{symbol} | signal={result.signal} | action={action} | reason={result.reason}",
                )
            if not result.executed and result.signal != "WAIT":
                self._log("INFO", f"{symbol}: no se operó ({result.reason})")
