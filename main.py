"""Punto de entrada de PIA 2.0.
 
Uso:
    python main.py
 
Lee config/config.yaml y .env, conecta a MetaTrader 5 y arranca el loop
autónomo. En modo demo no envía órdenes reales; en modo real sí (según
'mode' en config.yaml).
"""
 
from __future__ import annotations

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import TextIO


class _TeeStream:
    """Keep terminal output while copying each completed line to the log."""

    _pia2_tee = True

    def __init__(self, stream: TextIO, logger: logging.Logger, level: int):
        self._stream = stream
        self._logger = logger
        self._level = level
        self._pending = ""

    @property
    def encoding(self):
        return self._stream.encoding

    @property
    def errors(self):
        return self._stream.errors

    def write(self, text: str) -> int:
        parts = (self._pending + text).splitlines(keepends=True)
        self._pending = ""
        if parts and not parts[-1].endswith(("\n", "\r")):
            self._pending = parts.pop()
        for line in parts:
            self._logger.log(self._level, line.rstrip("\r\n"))
        try:
            return self._stream.write(text)
        except Exception:
            if self._pending:
                self._logger.log(self._level, self._pending)
                self._pending = ""
            raise

    def flush(self) -> None:
        if self._pending:
            self._logger.log(self._level, self._pending)
            self._pending = ""
        self._stream.flush()

    def isatty(self) -> bool:
        return self._stream.isatty()

    def fileno(self) -> int:
        return self._stream.fileno()


def _configure_console_logging() -> None:
    log_path = Path(__file__).resolve().parent / "logs" / "pia2.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("pia2.console")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(
        isinstance(handler, RotatingFileHandler)
        and handler.baseFilename == str(log_path.resolve())
        for handler in logger.handlers
    ):
        handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    if not getattr(sys.stdout, "_pia2_tee", False):
        sys.stdout = _TeeStream(sys.stdout, logger, logging.INFO)
    if not getattr(sys.stderr, "_pia2_tee", False):
        sys.stderr = _TeeStream(sys.stderr, logger, logging.ERROR)


_configure_console_logging()

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
