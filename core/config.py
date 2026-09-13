"""Configuración de Magnus: carpeta de datos por SO y ajustes del usuario.

Prioridad: variable de entorno > `config.json` en la carpeta de datos > valor por
defecto. La carpeta de datos guarda conversaciones, skills, memoria y el
registro del medidor; nunca sale de la máquina.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path


def data_dir() -> Path:
    """Carpeta de datos del usuario según el sistema operativo."""
    env = os.environ.get("MAGNUS_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Magnus"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Magnus"
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "magnus"


@dataclass(frozen=True)
class Settings:
    ollama_url: str = "http://127.0.0.1:11434"
    host: str = "127.0.0.1"
    port: int = 8420
    # Obligatorio si el daemon escucha fuera de loopback.
    api_token: str | None = None

    # --- Medidor ---
    # Los precios de la nube están en USD; `usd_exchange_rate` convierte para
    # mostrar (p. ej. 18.5 para MXN). La tarifa eléctrica va en USD por kWh.
    currency: str = "USD"
    usd_exchange_rate: float = 1.0
    electricity_usd_per_kwh: float = 0.15
    # None: usar el precio de referencia de la familia de hardware.
    hardware_cost_usd: float | None = None
    hardware_lifetime_years: float = 3.0
    hours_per_day: float = 4.0
    # "auto" elige el modelo de nube de tamaño comparable al local.
    cloud_reference: str = "auto"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["api_token"] = "***" if self.api_token else None
        return data


_ENV_OVERRIDES = {
    "ollama_url": "MAGNUS_OLLAMA_URL",
    "host": "MAGNUS_HOST",
    "port": "MAGNUS_PORT",
    "api_token": "MAGNUS_API_TOKEN",
    "electricity_usd_per_kwh": "MAGNUS_ELECTRICITY_USD_PER_KWH",
}

_CONFIG_FILE = "config.json"


def _coerce(name: str, value: object) -> object:
    """Convierte al tipo del campo; los valores de entorno llegan como texto."""
    default = getattr(Settings(), name)
    if value is None:
        return None
    if isinstance(default, bool):
        return str(value).lower() in ("1", "true", "yes", "si", "sí")
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float) or name == "hardware_cost_usd":
        return float(value)
    return str(value)


def load_settings(directory: Path | None = None) -> Settings:
    directory = directory or data_dir()
    settings = Settings()
    path = directory / _CONFIG_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    known = {f.name for f in fields(Settings)}
    updates = {k: _coerce(k, v) for k, v in raw.items() if k in known}
    for name, env in _ENV_OVERRIDES.items():
        value = os.environ.get(env)
        if value:
            updates[name] = _coerce(name, value)
    return replace(settings, **updates)


def save_settings(changes: dict, directory: Path | None = None) -> Settings:
    """Aplica `changes` sobre el config.json existente y lo guarda."""
    directory = directory or data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _CONFIG_FILE
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        current = {}
    known = {f.name for f in fields(Settings)}
    unknown = set(changes) - known
    if unknown:
        raise ValueError(f"Ajustes desconocidos: {', '.join(sorted(unknown))}")
    current.update({k: _coerce(k, v) for k, v in changes.items()})
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    return load_settings(directory)
