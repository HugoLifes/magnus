"""Acceso al daemon cuando sale de la máquina.

Por omisión el daemon escucha solo en loopback y no pide nada: es la API local
de quien está sentado frente al equipo. En cuanto se expone a la red (el móvil
en la misma Wi-Fi, un servidor B200 compartido) cualquiera en esa red podría
leer conversaciones, documentos indexados y cargar modelos. Por eso:

- escuchar fuera de loopback exige un token (`magnus token new`);
- con token configurado, toda petición salvo `/health` lo lleva en
  `Authorization: Bearer <token>`, en `X-Magnus-Token` o, para el WebSocket
  y los navegadores, en `?token=`.
"""

from __future__ import annotations

import ipaddress
import secrets
from collections.abc import Mapping

TOKEN_HEADER = "x-magnus-token"
PUBLIC_PATHS = frozenset({"/health"})


def generate_token() -> str:
    """Token aleatorio de 256 bits, apto para URL."""
    return secrets.token_urlsafe(32)


def is_loopback(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def bind_error(host: str, token: str | None) -> str | None:
    """Mensaje si no es seguro escuchar en `host` con esta configuración."""
    if is_loopback(host) or token:
        return None
    return (f"Escuchar en {host} expone el daemon a la red sin protección. "
            "Crea un token con `magnus token new` o usa --host 127.0.0.1.")


def supplied_token(headers: Mapping[str, str], query: Mapping[str, str]) -> str | None:
    """Token de la petición: cabecera Authorization, X-Magnus-Token o ?token=."""
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return headers.get(TOKEN_HEADER) or query.get("token") or None


def token_ok(expected: str | None, headers: Mapping[str, str], query: Mapping[str, str]) -> bool:
    """True si no hay token configurado o si el de la petición coincide."""
    if not expected:
        return True
    supplied = supplied_token(headers, query)
    return supplied is not None and secrets.compare_digest(supplied, expected)
