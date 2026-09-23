"""La versión de Magnus, en un solo sitio.

Estaba repetida en `pyproject.toml`, en dos puntos del daemon y en el `pubspec`
de la app. Cuatro sitios para el mismo dato es un sitio donde equivocarse: el
día que uno se queda atrás, el usuario que reporta un fallo dice una versión y
el daemon responde otra.

Aquí vive la de Python (núcleo, daemon y CLI). Las de `pyproject.toml` y del
cliente Flutter no pueden importar este módulo, así que un test comprueba que
las tres coinciden (`tests/test_version.py`).

Formato: el de Python (PEP 440) para el paquete —`0.9.0b1`— y su equivalente en
SemVer para la app y las etiquetas de git —`0.9.0-beta.1`—.
"""

from __future__ import annotations

import re

__version__ = "0.9.0b1"

_PEP440 = re.compile(r"^(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?$")
_SUFIJOS = {"a": "alpha", "b": "beta", "rc": "rc"}


def semver(version: str | None = None) -> str:
    """La misma versión en SemVer: `0.9.0b1` → `0.9.0-beta.1`."""
    match = _PEP440.match(version or __version__)
    if not match:
        raise ValueError(f"Versión no reconocida: {version or __version__}")
    base, etapa, numero = match.groups()
    return base if etapa is None else f"{base}-{_SUFIJOS[etapa]}.{numero}"


def tag(version: str | None = None) -> str:
    """La etiqueta de git de esta versión: `v0.9.0-beta.1`."""
    return f"v{semver(version)}"


def is_prerelease(version: str | None = None) -> bool:
    """True si es alpha, beta o candidata: no va a producción sin decirlo."""
    return _PEP440.match(version or __version__).group(2) is not None
