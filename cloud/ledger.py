"""Libro mayor de créditos en SQLite: el saldo es la suma de movimientos, nunca un campo.

Guardar el saldo como una columna que se sobrescribe pierde la historia y abre
la puerta a condiciones de carrera entre dos peticiones simultáneas. Aquí cada
recarga, bono, cobro y vale es una fila; el saldo se calcula. `(account_id, ref)`
es único: un mismo vale, bono mensual o petición no se aplica dos veces.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from cloud.packs import FREE_MONTHLY_CREDITS, MILLI, PACKS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    created_at  REAL NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  TEXT NOT NULL REFERENCES accounts(id),
    kind        TEXT NOT NULL,          -- grant | topup | debit | adjust
    amount_mc   INTEGER NOT NULL,       -- positivo suma, negativo resta
    ref         TEXT NOT NULL,
    meta        TEXT,
    created_at  REAL NOT NULL,
    UNIQUE (account_id, ref)
);
CREATE INDEX IF NOT EXISTS idx_entries_account ON entries(account_id, id);
CREATE TABLE IF NOT EXISTS vouchers (
    code_hash    TEXT PRIMARY KEY,
    pack_id      TEXT NOT NULL,
    credits      INTEGER NOT NULL,
    created_at   REAL NOT NULL,
    redeemed_by  TEXT,
    redeemed_at  REAL
);
"""

# Crockford base32: sin I, L, O ni U, para dictar un vale por teléfono sin errores.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    created_at: float
    active: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_code(code: str) -> str:
    """'mag-7k2p 9x..' → 'MAG7K2P9X..'; confunde O con 0 e I/L con 1 a propósito."""
    raw = "".join(ch for ch in code.upper() if ch.isalnum())
    # Por longitud y no por prefijo: el cuerpo aleatorio también puede empezar con "MAG".
    body = raw[3:] if len(raw) == 15 else raw
    return "MAG" + body.translate(str.maketrans({"O": "0", "I": "1", "L": "1"}))


def _new_code() -> str:
    chars = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return f"MAG-{chars[:4]}-{chars[4:8]}-{chars[8:]}"


def month_ref(now: float | None = None) -> str:
    moment = datetime.fromtimestamp(now if now is not None else time.time(), tz=timezone.utc)
    return f"gratis-{moment:%Y-%m}"


class Ledger:
    """Seguro entre hilos: el gateway atiende peticiones concurrentes."""

    def __init__(self, path: Path | str) -> None:
        in_memory = str(path) == ":memory:"
        if not in_memory:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        if not in_memory:
            self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    # --- cuentas ----------------------------------------------------------

    def create_account(self, name: str) -> tuple[Account, str]:
        """Crea una cuenta y devuelve su clave. La clave solo se ve esta vez."""
        key = "mgk_" + secrets.token_urlsafe(32)
        account = Account(id=uuid.uuid4().hex[:16], name=name.strip() or "Sin nombre",
                          created_at=time.time(), active=True)
        with self._lock, self._db:
            self._db.execute("INSERT INTO accounts VALUES (?, ?, ?, ?, 1)",
                             (account.id, account.name, _hash(key), account.created_at))
        return account, key

    def account_by_key(self, key: str) -> Account | None:
        with self._lock:
            row = self._db.execute(
                "SELECT id, name, created_at, active FROM accounts WHERE key_hash = ?",
                (_hash(key),)).fetchone()
        if row is None or not row["active"]:
            return None
        return Account(row["id"], row["name"], row["created_at"], bool(row["active"]))

    def get_account(self, account_id: str) -> Account | None:
        with self._lock:
            row = self._db.execute(
                "SELECT id, name, created_at, active FROM accounts WHERE id = ?",
                (account_id,)).fetchone()
        return Account(row["id"], row["name"], row["created_at"], bool(row["active"])) \
            if row else None

    # --- movimientos ------------------------------------------------------

    def balance_mc(self, account_id: str) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(SUM(amount_mc), 0) AS s FROM entries WHERE account_id = ?",
                (account_id,)).fetchone()
        return int(row["s"])

    def add(self, account_id: str, kind: str, amount_mc: int, ref: str,
            meta: dict | None = None) -> bool:
        """Registra un movimiento. False si esa `ref` ya estaba aplicada a la cuenta."""
        try:
            with self._lock, self._db:
                self._db.execute(
                    "INSERT INTO entries (account_id, kind, amount_mc, ref, meta, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (account_id, kind, amount_mc, ref,
                     json.dumps(meta, ensure_ascii=False) if meta else None, time.time()))
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                return False
            raise LedgerError(f"Cuenta inexistente: {account_id}") from exc
        return True

    def ensure_monthly_grant(self, account_id: str, now: float | None = None) -> bool:
        """Da el bono gratuito del mes si aún no se dio. Idempotente."""
        return self.add(account_id, "grant", FREE_MONTHLY_CREDITS * MILLI, month_ref(now),
                        {"motivo": "bono mensual gratuito"})

    def debit(self, account_id: str, amount_mc: int, request_id: str, meta: dict) -> bool:
        return self.add(account_id, "debit", -abs(amount_mc), f"req-{request_id}", meta)

    def history(self, account_id: str, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, amount_mc, ref, meta, created_at FROM entries "
                "WHERE account_id = ? ORDER BY id DESC LIMIT ?", (account_id, limit)).fetchall()
        return [{"kind": r["kind"], "credits": round(r["amount_mc"] / MILLI, 3),
                 "ref": r["ref"], "meta": json.loads(r["meta"]) if r["meta"] else None,
                 "created_at": r["created_at"]} for r in rows]

    # --- vales ------------------------------------------------------------

    def create_vouchers(self, pack_id: str, count: int) -> list[str]:
        """Emite vales de un paquete. Los códigos solo se devuelven aquí: se guarda su hash."""
        pack = PACKS.get(pack_id)
        if pack is None:
            raise LedgerError(f"Paquete desconocido: {pack_id}. Opciones: {', '.join(PACKS)}")
        if not 1 <= count <= 1000:
            raise LedgerError("Se emiten entre 1 y 1000 vales por vez.")
        codes = [_new_code() for _ in range(count)]
        now = time.time()
        with self._lock, self._db:
            self._db.executemany(
                "INSERT INTO vouchers (code_hash, pack_id, credits, created_at) VALUES (?,?,?,?)",
                [(_hash(normalize_code(c)), pack.id, pack.credits, now) for c in codes])
        return codes

    def redeem(self, account_id: str, code: str) -> int:
        """Canjea un vale. Devuelve los créditos sumados. Un vale sirve una sola vez."""
        code_hash = _hash(normalize_code(code))
        now = time.time()
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT pack_id, credits, redeemed_by FROM vouchers WHERE code_hash = ?",
                (code_hash,)).fetchone()
            if row is None:
                raise LedgerError("Ese código no existe. Revisa que esté completo.")
            if row["redeemed_by"]:
                raise LedgerError("Ese código ya se canjeó.")
            # La condición `redeemed_by IS NULL` evita el doble canje entre hilos.
            cur = self._db.execute(
                "UPDATE vouchers SET redeemed_by = ?, redeemed_at = ? "
                "WHERE code_hash = ? AND redeemed_by IS NULL", (account_id, now, code_hash))
            if cur.rowcount != 1:
                raise LedgerError("Ese código ya se canjeó.")
            self._db.execute(
                "INSERT INTO entries (account_id, kind, amount_mc, ref, meta, created_at) "
                "VALUES (?, 'topup', ?, ?, ?, ?)",
                (account_id, row["credits"] * MILLI, f"vale-{code_hash[:16]}",
                 json.dumps({"paquete": row["pack_id"]}), now))
        return int(row["credits"])
