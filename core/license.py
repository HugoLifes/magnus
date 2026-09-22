"""Licencias de Magnus: firmadas, verificadas sin internet.

Magnus se vende para correr en la máquina del cliente, muchas veces sin red. Por
eso la licencia **no se consulta a un servidor**: es un texto firmado con Ed25519
que el daemon verifica con una clave pública que lleva dentro. Quien firma es el
emisor (la función sin servidor que atiende el webhook de la pasarela), y su
clave privada nunca vive en el repo ni en la app.

Formato del texto de licencia:

    MAGNUS1.<contenido en base64url>.<firma en base64url>

El contenido es un JSON compacto con claves ordenadas, para que firmar y
verificar produzcan siempre los mismos bytes.

Vencimiento y gracia: una licencia vencida sigue funcionando [GRACE_DAYS] días,
para que a nadie se le apague la herramienta por un cobro que tardó un día.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PREFIX = "MAGNUS1"
GRACE_DAYS = 14
_GRACE_S = GRACE_DAYS * 86400

# Orden de los planes: cada uno incluye lo del anterior.
PLANS = ("community", "pro", "team")

# Clave pública del emisor. **Es de desarrollo**: antes de vender hay que generar
# el par definitivo (`magnus license keygen`), guardar la privada en el emisor y
# reemplazar esta constante. `MAGNUS_LICENSE_PUBKEY` la sobrescribe para pruebas
# y para rotarla sin recompilar.
DEV_PUBLIC_KEY_HEX = "7b1e7fde0a48eaaf97d7c643fd66762bc69184fd07ac7f7d12a4fe0e22470f7b"


class LicenseError(Exception):
    """La licencia no se puede usar. El mensaje explica por qué, en español."""


@dataclass(frozen=True)
class License:
    """Lo que dice una licencia ya verificada."""

    id: str
    plan: str
    holder: str
    issued: float
    expires: float | None = None
    seats: int = 1
    notes: str = ""
    raw: str = field(default="", repr=False, compare=False)

    # --- Vigencia ---------------------------------------------------------
    def status(self, now: float | None = None) -> str:
        """`activa`, `en gracia` o `vencida`."""
        if self.expires is None:
            return "activa"
        t = time.time() if now is None else now
        if t <= self.expires:
            return "activa"
        return "en gracia" if t <= self.expires + _GRACE_S else "vencida"

    def effective_plan(self, now: float | None = None) -> str:
        """Plan que vale ahora mismo: una licencia vencida cae a community."""
        return "community" if self.status(now) == "vencida" else self.plan

    def days_left(self, now: float | None = None) -> int | None:
        """Días hasta el vencimiento; negativos si está en gracia."""
        if self.expires is None:
            return None
        t = time.time() if now is None else now
        return int((self.expires - t) // 86400)

    def to_dict(self, now: float | None = None) -> dict:
        return {
            "id": self.id,
            "plan": self.plan,
            "effective_plan": self.effective_plan(now),
            "holder": self.holder,
            "issued": self.issued,
            "expires": self.expires,
            "seats": self.seats,
            "notes": self.notes,
            "status": self.status(now),
            "days_left": self.days_left(now),
        }


COMMUNITY = License(id="community", plan="community", holder="", issued=0.0)


def plan_allows(have: str, needed: str) -> bool:
    """True si el plan `have` incluye lo que pide `needed`."""
    try:
        return PLANS.index(have) >= PLANS.index(needed)
    except ValueError as exc:  # plan desconocido: se trata como community
        raise LicenseError(f"Plan desconocido: {have!r}. Válidos: {', '.join(PLANS)}.") from exc


# ---------------------------------------------------------------------------
# Firma y verificación
# ---------------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def generate_keypair() -> tuple[str, str]:
    """Par nuevo (privada, pública) en hexadecimal. La privada vive en el emisor."""
    private = Ed25519PrivateKey.generate()
    return (
        private.private_bytes_raw().hex(),
        private.public_key().public_bytes_raw().hex(),
    )


def sign_license(payload: dict, private_key_hex: str) -> str:
    """Firma un contenido de licencia. Lo usa el emisor, no la app del cliente."""
    body = _canonical(payload)
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    return f"{PREFIX}.{_b64(body)}.{_b64(key.sign(body))}"


def public_key_hex() -> str:
    """Clave pública en uso: la del entorno si está, si no la incluida."""
    return os.environ.get("MAGNUS_LICENSE_PUBKEY", DEV_PUBLIC_KEY_HEX).strip()


def verify_license(text: str, *, public_key: str | None = None) -> License:
    """Verifica el texto de una licencia y devuelve lo que dice.

    Lanza [LicenseError] si el formato no cuadra, si la firma no corresponde o
    si faltan campos. No mira el vencimiento: de eso se encarga `License.status`.
    """
    parts = (text or "").strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise LicenseError("Ese texto no parece una licencia de Magnus.")
    try:
        body = _unb64(parts[1])
        signature = _unb64(parts[2])
    except (ValueError, TypeError) as exc:
        raise LicenseError("La licencia está corrupta: no se pudo leer su contenido.") from exc

    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key or public_key_hex()))
    except ValueError as exc:
        raise LicenseError("La clave pública de licencias no es válida.") from exc

    try:
        key.verify(signature, body)
    except InvalidSignature as exc:
        raise LicenseError(
            "La firma de la licencia no es válida. ¿La copiaste completa?"
        ) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LicenseError("La licencia está corrupta: su contenido no es JSON.") from exc

    plan = str(payload.get("plan", "")).lower()
    if plan not in PLANS:
        raise LicenseError(f"La licencia trae un plan desconocido: {plan!r}.")
    if not payload.get("id"):
        raise LicenseError("La licencia no trae identificador.")

    expires = payload.get("expires")
    return License(
        id=str(payload["id"]),
        plan=plan,
        holder=str(payload.get("holder", "")),
        issued=float(payload.get("issued", 0.0)),
        expires=None if expires is None else float(expires),
        seats=int(payload.get("seats", 1)),
        notes=str(payload.get("notes", "")),
        raw=text.strip(),
    )


# ---------------------------------------------------------------------------
# Dónde vive la licencia del equipo
# ---------------------------------------------------------------------------


class LicenseStore:
    """Guarda la licencia activa del equipo en un archivo de texto."""

    FILENAME = "license.txt"

    def __init__(self, home: Path) -> None:
        self._path = Path(home) / self.FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def current(self) -> License:
        """Licencia guardada, o la de Community si no hay o no verifica."""
        try:
            return verify_license(self._path.read_text(encoding="utf-8"))
        except (OSError, LicenseError):
            return COMMUNITY

    def activate(self, text: str) -> License:
        """Verifica y guarda. Devuelve la licencia; lanza [LicenseError] si no vale."""
        lic = verify_license(text)
        if lic.status() == "vencida":
            raise LicenseError(
                f"Esa licencia venció hace más de {GRACE_DAYS} días. Renuévala para activarla."
            )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(lic.raw, encoding="utf-8")
        return lic

    def deactivate(self) -> None:
        self._path.unlink(missing_ok=True)


def upgrade_message(needed: str) -> str:
    """Texto que ve quien pide una función que no cubre su plan."""
    if needed == "pro":
        return (
            "Esta función es de Magnus Pro: tus documentos indexados con citas, el agente de "
            "código en modo autónomo y el índice del repositorio. Actívala con "
            "`magnus license activate <archivo>` o pruébala 14 días desde la app."
        )
    if needed == "team":
        return (
            "Esta función es de Magnus Team: reglas de permisos de la organización y bitácora "
            "de auditoría. Escribe a ventas para una licencia por equipo."
        )
    return f"Esta función necesita el plan {needed}."
