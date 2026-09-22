"""Conversaciones y registro del medidor en SQLite.

Un solo archivo en la carpeta de datos del usuario, cero servidores. Cada
respuesta del asistente guarda sus métricas (tokens, energía, coste local y
nube), así el "ahorro acumulado" se calcula sobre lo que de verdad pasó.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    model       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      REAL NOT NULL,
    metrics         TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS turns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    created_at  REAL NOT NULL,
    metrics     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_created ON turns(created_at);
"""

_TITLE_CHARS = 60


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    model: str
    created_at: float
    updated_at: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Message:
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: float
    metrics: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def title_from(text: str) -> str:
    """Título legible a partir del primer mensaje del usuario."""
    line = " ".join(text.split())
    if len(line) <= _TITLE_CHARS:
        return line or "Conversación nueva"
    return line[: _TITLE_CHARS - 1].rstrip() + "…"


class Store:
    """Acceso a la base. Seguro entre hilos: el daemon atiende en un pool."""

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

    # --- conversaciones ---------------------------------------------------

    def create_conversation(self, model: str, title: str) -> Conversation:
        now = time.time()
        conv = Conversation(id=uuid.uuid4().hex, title=title, model=model,
                            created_at=now, updated_at=now)
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                (conv.id, conv.title, conv.model, conv.created_at, conv.updated_at),
            )
        return conv

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return Conversation(**dict(row)) if row else None

    def list_conversations(self, limit: int = 100) -> list[Conversation]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Conversation(**dict(r)) for r in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        return cur.rowcount > 0

    # --- mensajes ---------------------------------------------------------

    def add_message(
        self, conversation_id: str, role: str, content: str, metrics: dict | None = None
    ) -> Message:
        now = time.time()
        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at, metrics) "
                "VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, now,
                 json.dumps(metrics) if metrics is not None else None),
            )
            self._db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id)
            )
        return Message(id=cur.lastrowid, conversation_id=conversation_id, role=role,
                       content=content, created_at=now, metrics=metrics)

    def messages(self, conversation_id: str) -> list[Message]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conversation_id,)
            ).fetchall()
        return [
            Message(**(dict(r) | {"metrics": json.loads(r["metrics"]) if r["metrics"] else None}))
            for r in rows
        ]

    # --- medidor ----------------------------------------------------------

    def record_turn(self, source: str, metrics: dict) -> None:
        """Registra un turno que no pertenece a una conversación.

        Lo usa el proxy de `/v1/messages`: cuando alguien programa con Claude
        Code contra esta GPU no hay conversación que guardar, pero el turno sí
        cuenta para el medidor y para el ahorro acumulado.
        """
        with self._lock:
            self._db.execute(
                "INSERT INTO turns (source, created_at, metrics) VALUES (?, ?, ?)",
                (source, time.time(), json.dumps(metrics, ensure_ascii=False)),
            )
            self._db.commit()

    def usage_summary(self, since: float | None = None) -> dict:
        """Totales del medidor: tokens, energía, coste local, nube y ahorro.

        Suma los turnos del chat (mensajes con medición) y los de `turns`, que
        vienen del proxy de la API de mensajes.
        """
        queries = [
            "SELECT metrics FROM messages WHERE metrics IS NOT NULL",
            "SELECT metrics FROM turns",
        ]
        params: tuple = ()
        if since is not None:
            queries = [f"{q} AND created_at >= ?" if "WHERE" in q else f"{q} WHERE created_at >= ?"
                       for q in queries]
            params = (since,)
        with self._lock:
            rows = [row for q in queries for row in self._db.execute(q, params).fetchall()]

        totals = _empty_totals()
        by_model: dict[str, dict] = {}
        for row in rows:
            m = json.loads(row["metrics"])
            _accumulate(totals, m)
            _accumulate(by_model.setdefault(m.get("model", "?"), _empty_totals()), m)
        return {
            **_rounded(totals),
            "by_model": [{"model": k, **_rounded(v)} for k, v in sorted(by_model.items())],
        }


def _empty_totals() -> dict:
    return {"turns": 0, "tokens_in": 0, "tokens_out": 0, "energy_wh": 0.0,
            "local_cost_usd": 0.0, "cloud_cost_usd": 0.0, "savings_usd": 0.0}


def _accumulate(acc: dict, m: dict) -> None:
    acc["turns"] += 1
    for key in ("tokens_in", "tokens_out", "energy_wh", "local_cost_usd",
                "cloud_cost_usd", "savings_usd"):
        acc[key] += m.get(key) or 0


def _rounded(acc: dict) -> dict:
    return {k: round(v, 6) if isinstance(v, float) else v for k, v in acc.items()}
