
"""Carga de variables de entorno desde un archivo .env (sin dependencias).
 
Las credenciales (MT5, Telegram) viven en .env y NUNCA en el YAML ni en el
código. Este loader es minimalista: KEY=VALUE por línea, ignora comentarios.
"""
 
from __future__ import annotations
 
import os
from pathlib import Path
 
 
def load_env(path: str | os.PathLike = ".env") -> dict[str, str]:
    env_path = Path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
 
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
        os.environ.setdefault(key, value)
    return values