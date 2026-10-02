"""Notificaciones (explicar 'qué hizo y por qué').
 
Interfaz para enviar mensajes. En Fase 0 se usa ConsoleNotifier; en fases
siguientes se añade TelegramNotifier con la misma interfaz.
"""
 
from __future__ import annotations
 
import logging
import os
from abc import ABC, abstractmethod
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests
 
 
class Notifier(ABC):
    @abstractmethod
    def send(self, message: str) -> None: ...
 
 
class ConsoleNotifier(Notifier):
    def send(self, message: str) -> None:
        print(message)


class FileRotatingNotifier(Notifier):
    def __init__(self, path: str = "logs/pia.log", max_bytes: int = 1_048_576, backup_count: int = 3):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("pia2")
        self.logger.setLevel(logging.INFO)
        if not any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == str(Path(path).resolve()) for h in self.logger.handlers):
            handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self.logger.addHandler(handler)

    def send(self, message: str) -> None:
        self.logger.info(message)


class TelegramNotifier(Notifier):
    def __init__(self, token: str | None = None, chat_id: str | None = None, base_url: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = base_url or "https://api.telegram.org"

    def send(self, message: str) -> None:
        if not self.token or not self.chat_id:
            return
        url = f"{self.base_url}/bot{self.token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.chat_id, "text": message}, timeout=5)
        except requests.RequestException:
            pass
