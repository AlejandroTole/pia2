
"""Cliente de LLM local (Ollama).
 
Se aísla detrás de una interfaz para poder sustituirlo por un mock en tests
(sin necesidad de tener Ollama corriendo).
"""
 
from __future__ import annotations
 
from abc import ABC, abstractmethod
import json
import shutil
import subprocess
import time

import requests


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str: ...
 
 
class OllamaClient(LLMClient):
    def __init__(self, model: str, base_url: str = "http://localhost:11434", timeout: int = 60):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.ensure_running()

    def _is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.ok
        except requests.RequestException:
            return False

    def ensure_running(self) -> bool:
        if self._is_available():
            return True

        binary = shutil.which("ollama") or shutil.which("ollama.exe")
        if not binary:
            return False

        try:
            subprocess.Popen(
                [binary, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            return False

        for _ in range(5):
            if self._is_available():
                return True
            time.sleep(1)
        return False

    def generate(self, prompt: str) -> str:
        if not self.ensure_running():
            return '{"signal": "WAIT", "confidence": 0, "reason": "Ollama no está disponible"}'

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            # format=json fuerza a Ollama a devolver JSON válido cuando el modelo
            # lo soporta, haciendo el parseo mucho más robusto que regex.
            "format": "json",
            "options": {"temperature": 0.2},
        }
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.RequestException as exc:
            return json.dumps({
                "signal": "WAIT",
                "confidence": 0,
                "reason": f"LLM timeout/error: {exc}",
            })