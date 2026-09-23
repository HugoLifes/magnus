"""Claves de proveedores (NVIDIA, Groq, OpenRouter, Magnus Cloud) fuera del config.json.

Las claves del usuario no van en `config.json` ni viajan por `/settings`. Se
guardan en el llavero del sistema operativo cuando existe — Administrador de
credenciales en Windows, Keychain en macOS, Secret Service en Linux con
escritorio — y si no, en `secrets.json` dentro de la carpeta de datos con
permisos solo para el usuario.

El respaldo en archivo no es un descuido: en un Jetson o dentro de Docker no hay
llavero, y ahí la carpeta de datos es un volumen que solo ve el contenedor.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

_SERVICE = "magnus"
_FILE = "secrets.json"


def _keyring():
    """El módulo keyring si hay un backend real; None si no (Docker, Jetson, CI)."""
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    try:
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
    except Exception:  # noqa: BLE001 — un backend roto equivale a no tener llavero
        return None
    return keyring


class SecretStore:
    def __init__(self, directory: Path, use_keyring: bool = True) -> None:
        self._path = Path(directory) / _FILE
        self._keyring = _keyring() if use_keyring else None

    @property
    def backend(self) -> str:
        return "llavero del sistema" if self._keyring else "archivo local"

    # --- archivo ----------------------------------------------------------

    def _read_file(self) -> dict[str, str]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_file(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        # En Windows chmod solo quita escritura; ahí protege que la carpeta de
        # datos cuelgue de %LOCALAPPDATA%, que es del usuario.
        with contextlib.suppress(OSError):
            os.chmod(self._path, 0o600)

    # --- API --------------------------------------------------------------

    def get(self, name: str) -> str | None:
        if self._keyring:
            try:
                value = self._keyring.get_password(_SERVICE, name)
            except Exception:  # noqa: BLE001
                value = None
            if value:
                return value
        return self._read_file().get(name)

    def set(self, name: str, value: str) -> None:
        stored = False
        if self._keyring:
            try:
                self._keyring.set_password(_SERVICE, name, value)
            except Exception:  # noqa: BLE001 — sin llavero usable, se usa el archivo
                stored = False
            else:
                stored = True
        if stored:
            # Si antes estaba en archivo, que no quede una copia vieja.
            self._delete_from_file(name)
            return
        data = self._read_file()
        data[name] = value
        self._write_file(data)

    def delete(self, name: str) -> None:
        if self._keyring:
            with contextlib.suppress(Exception):
                self._keyring.delete_password(_SERVICE, name)
        self._delete_from_file(name)

    def _delete_from_file(self, name: str) -> None:
        data = self._read_file()
        if name in data:
            del data[name]
            self._write_file(data)
