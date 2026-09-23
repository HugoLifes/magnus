"""Memoria y mini-RAG local: tus documentos y tus datos, buscados por significado.

Todo en la máquina: los embeddings los calcula un modelo de Ollama (por omisión
`nomic-embed-text`, 274 MB, cabe en cualquier equipo de la familia NVIDIA) y los
vectores se guardan en SQLite junto a las conversaciones.

La búsqueda es por coseno sobre los vectores de la colección: con numpy si está
instalado, en Python puro si no. Para una colección personal (miles de
fragmentos) alcanza, y evita depender de extensiones nativas de SQLite que no
todas las builds de Python en Windows permiten cargar.

Dos piezas:
- **Colecciones**: documentos troceados en fragmentos (RAG).
- **Memoria**: hechos cortos que el usuario quiere que Magnus recuerde.
"""

from __future__ import annotations

import hashlib
import heapq
import html
import math
import re
import sqlite3
import threading
import time
import uuid
from array import array
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from core.runtime_manager import RuntimeManagerError

DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_CHUNK_CHARS = 1000
DEFAULT_OVERLAP_CHARS = 150
MAX_FILE_BYTES = 20 * 1024 * 1024
_EMBED_BATCH = 32

TEXT_SUFFIXES = frozenset({
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".log", ".xml", ".html", ".htm", ".sql", ".sh", ".ps1", ".bat",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".dart", ".java", ".kt", ".go", ".rs", ".c",
    ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift",
})
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | {".pdf"}

Embedder = Callable[[list[str]], list[list[float]]]


class RagError(Exception):
    """Error con un mensaje para el usuario."""


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class OllamaEmbedder:
    """Embeddings con /api/embed de Ollama, por lotes.

    `before` recibe el modelo antes de calcular: el daemon pasa
    `RuntimeManager.ensure_loaded`, porque en equipos donde cabe un solo modelo
    (Jetson) Ollama cargaría el de embeddings sin guarda de memoria.
    """

    def __init__(self, base_url: str, model: str = DEFAULT_EMBEDDING_MODEL,
                 before: Callable[[str], object] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._before = before

    def __call__(self, texts: list[str]) -> list[list[float]]:
        if self._before:
            try:
                self._before(self.model)
            except RuntimeManagerError as exc:
                raise RagError(str(exc)) from exc
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i:i + _EMBED_BATCH]
            try:
                r = httpx.post(f"{self.base_url}/api/embed",
                               json={"model": self.model, "input": batch}, timeout=300)
            except httpx.ConnectError as exc:
                raise RagError(f"No se puede conectar con Ollama en {self.base_url}.") from exc
            if r.status_code == 404:
                raise RagError(f"Falta el modelo de embeddings '{self.model}'. "
                               f"Descárgalo con: magnus fetch {self.model}")
            if r.status_code >= 400:
                raise RagError(f"Ollama respondió {r.status_code} al calcular embeddings: {r.text}")
            vectors += r.json().get("embeddings", [])
        if len(vectors) != len(texts):
            raise RagError("Ollama devolvió un número de embeddings distinto al de textos.")
        return vectors


def _normalized(vector: list[float]) -> array:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return array("f", (x / norm for x in vector))


try:  # numpy acelera la búsqueda, pero no es obligatorio
    import numpy as _np
except ImportError:  # pragma: no cover - depende del entorno
    _np = None


def _top_k(query: array, rows: list[tuple], k: int) -> list[tuple[float, tuple]]:
    """(score, fila) de las k filas más parecidas. `rows[i][-1]` es el blob del vector."""
    if not rows:
        return []
    if _np is not None:
        matrix = _np.stack([_np.frombuffer(r[-1], dtype=_np.float32) for r in rows])
        scores = matrix @ _np.frombuffer(query.tobytes(), dtype=_np.float32)
        order = _np.argsort(-scores)[:k]
        return [(float(scores[i]), rows[i]) for i in order]
    scored = []
    for row in rows:
        vec = array("f")
        vec.frombytes(row[-1])
        scored.append((sum(a * b for a, b in zip(query, vec)), row))
    return heapq.nlargest(k, scored, key=lambda s: s[0])


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------


def chunk_text(text: str, chunk_chars: int = DEFAULT_CHUNK_CHARS,
               overlap_chars: int = DEFAULT_OVERLAP_CHARS) -> list[str]:
    """Trocea por párrafos hasta ~chunk_chars, con solapamiento entre fragmentos.

    El solapamiento evita que una idea partida en la frontera se pierda en la
    búsqueda. Los párrafos más largos que un fragmento se cortan por frases.
    """
    if chunk_chars <= 0:
        raise RagError("El tamaño de fragmento debe ser positivo.")
    overlap_chars = max(0, min(overlap_chars, chunk_chars // 2))
    pieces: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= chunk_chars:
            pieces.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?…])\s+", paragraph)
        for sentence in sentences:
            while len(sentence) > chunk_chars:
                pieces.append(sentence[:chunk_chars])
                sentence = sentence[chunk_chars:]
            if sentence:
                pieces.append(sentence)

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n\n{piece}" if current else piece
        if len(candidate) <= chunk_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars else ""
            if " " in tail:
                tail = tail[tail.index(" ") + 1:]  # no empezar a mitad de palabra
            current = f"{tail} {piece}".strip() if tail else piece
            if len(current) > chunk_chars:
                current = piece
        else:
            current = piece
    if current:
        chunks.append(current)
    return chunks


def extract_text(path: Path) -> str:
    """Texto de un archivo soportado. PDF requiere `pypdf`."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise RagError(f"Tipo de archivo no soportado: {path.name}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise RagError(f"{path.name} pasa de {MAX_FILE_BYTES // 1024**2} MB.")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RagError("Para indexar PDFs instala pypdf: pip install pypdf") from exc
        return "\n\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix in (".html", ".htm"):
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        text = re.sub(r"[ \t]+", " ", text)
    return text


# ---------------------------------------------------------------------------
# Almacén
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_collections (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    embedding_model TEXT NOT NULL,
    chunk_chars     INTEGER NOT NULL,
    overlap_chars   INTEGER NOT NULL,
    created_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rag_documents (
    id            TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES rag_collections(id) ON DELETE CASCADE,
    source        TEXT NOT NULL,
    title         TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    created_at    REAL NOT NULL,
    UNIQUE (collection_id, sha256)
);
CREATE TABLE IF NOT EXISTS rag_chunks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id   TEXT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    collection_id TEXT NOT NULL,
    ordinal       INTEGER NOT NULL,
    text          TEXT NOT NULL,
    embedding     BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_collection ON rag_chunks(collection_id);
CREATE TABLE IF NOT EXISTS memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    text            TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding       BLOB NOT NULL,
    created_at      REAL NOT NULL
);
"""


@dataclass(frozen=True)
class Collection:
    id: str
    name: str
    embedding_model: str
    chunk_chars: int
    overlap_chars: int
    created_at: float
    documents: int = 0
    chunks: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchHit:
    score: float
    text: str
    source: str
    title: str
    ordinal: int
    document_id: str

    def to_dict(self) -> dict:
        return asdict(self) | {"score": round(self.score, 4)}


@dataclass(frozen=True)
class Memory:
    id: int
    text: str
    created_at: float
    score: float | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.score is None:
            data.pop("score")
        else:
            data["score"] = round(self.score, 4)
        return data


class RagStore:
    """Colecciones, documentos, fragmentos y memoria. Seguro entre hilos."""

    def __init__(
        self,
        path: Path | str,
        embedder_factory: Callable[[str], Embedder],
        memory_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        in_memory = str(path) == ":memory:"
        if not in_memory:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._embedder_factory = embedder_factory
        self._memory_model = memory_model
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        if not in_memory:
            self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    # --- colecciones -------------------------------------------------------

    def create_collection(
        self,
        name: str,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        chunk_chars: int = DEFAULT_CHUNK_CHARS,
        overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    ) -> Collection:
        name = name.strip()
        if not name or len(name) > 80:
            raise RagError("El nombre de la colección debe tener entre 1 y 80 caracteres.")
        if chunk_chars < 100 or not 0 <= overlap_chars < chunk_chars:
            raise RagError("Fragmentos de al menos 100 caracteres y solapamiento menor que el fragmento.")
        coll = Collection(uuid.uuid4().hex, name, embedding_model, chunk_chars, overlap_chars,
                          time.time())
        try:
            with self._lock, self._db:
                self._db.execute(
                    "INSERT INTO rag_collections VALUES (?, ?, ?, ?, ?, ?)",
                    (coll.id, coll.name, coll.embedding_model, coll.chunk_chars,
                     coll.overlap_chars, coll.created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise RagError(f"Ya existe una colección llamada '{name}'.") from exc
        return coll

    def list_collections(self) -> list[Collection]:
        with self._lock:
            rows = self._db.execute(
                """SELECT c.*,
                          (SELECT COUNT(*) FROM rag_documents d WHERE d.collection_id = c.id)
                              AS documents,
                          (SELECT COUNT(*) FROM rag_chunks k WHERE k.collection_id = c.id)
                              AS chunks
                   FROM rag_collections c ORDER BY c.name"""
            ).fetchall()
        return [Collection(**dict(r)) for r in rows]

    def get_collection(self, name: str) -> Collection:
        for coll in self.list_collections():
            if coll.name == name:
                return coll
        raise RagError(f"No existe la colección '{name}'.")

    def delete_collection(self, name: str) -> None:
        coll = self.get_collection(name)
        with self._lock, self._db:
            self._db.execute("DELETE FROM rag_chunks WHERE collection_id = ?", (coll.id,))
            self._db.execute("DELETE FROM rag_collections WHERE id = ?", (coll.id,))

    # --- ingesta ------------------------------------------------------------

    def ingest_text(self, collection: str, text: str, source: str,
                    title: str | None = None) -> dict:
        """Indexa un texto. Si ya estaba (mismo contenido), no lo repite."""
        coll = self.get_collection(collection)
        if not text.strip():
            raise RagError(f"{source}: no tiene texto que indexar.")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self._lock:
            existing = self._db.execute(
                "SELECT id FROM rag_documents WHERE collection_id = ? AND sha256 = ?",
                (coll.id, digest),
            ).fetchone()
        if existing:
            return {"source": source, "document_id": existing["id"], "chunks": 0, "skipped": True}

        chunks = chunk_text(text, coll.chunk_chars, coll.overlap_chars)
        vectors = self._embedder_factory(coll.embedding_model)(chunks)
        doc_id = uuid.uuid4().hex
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO rag_documents VALUES (?, ?, ?, ?, ?, ?)",
                (doc_id, coll.id, source, title or Path(source).name or source, digest, time.time()),
            )
            self._db.executemany(
                "INSERT INTO rag_chunks (document_id, collection_id, ordinal, text, embedding) "
                "VALUES (?, ?, ?, ?, ?)",
                [(doc_id, coll.id, i, chunk, _normalized(vec).tobytes())
                 for i, (chunk, vec) in enumerate(zip(chunks, vectors))],
            )
        return {"source": source, "document_id": doc_id, "chunks": len(chunks), "skipped": False}

    def ingest_path(self, collection: str, path: Path) -> dict:
        """Indexa un archivo o una carpeta (recursiva). Los errores no detienen el resto."""
        path = Path(path)
        if not path.exists():
            raise RagError(f"No existe: {path}")
        files = [path] if path.is_file() else sorted(
            p for p in path.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
            and not any(part.startswith(".") for part in p.relative_to(path).parts)
        )
        results, errors = [], {}
        for f in files:
            try:
                results.append(self.ingest_text(collection, extract_text(f), str(f), f.name))
            except (RagError, OSError) as exc:
                errors[str(f)] = str(exc)
        return {
            "indexed": sum(1 for r in results if not r["skipped"]),
            "skipped": sum(1 for r in results if r["skipped"]),
            "chunks": sum(r["chunks"] for r in results),
            "errors": errors,
        }

    def delete_document(self, collection: str, document_id: str) -> bool:
        coll = self.get_collection(collection)
        with self._lock, self._db:
            cur = self._db.execute(
                "DELETE FROM rag_documents WHERE id = ? AND collection_id = ?",
                (document_id, coll.id),
            )
        return cur.rowcount > 0

    def list_documents(self, collection: str) -> list[dict]:
        coll = self.get_collection(collection)
        with self._lock:
            rows = self._db.execute(
                """SELECT d.id, d.source, d.title, d.created_at,
                          (SELECT COUNT(*) FROM rag_chunks k WHERE k.document_id = d.id) AS chunks
                   FROM rag_documents d WHERE d.collection_id = ? ORDER BY d.created_at""",
                (coll.id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- búsqueda -----------------------------------------------------------

    def search(self, collection: str, query: str, k: int = 5) -> list[SearchHit]:
        coll = self.get_collection(collection)
        if not query.strip():
            return []
        q = _normalized(self._embedder_factory(coll.embedding_model)([query])[0])
        with self._lock:
            rows = self._db.execute(
                """SELECT k.text, d.source, d.title, k.ordinal, k.document_id, k.embedding
                   FROM rag_chunks k JOIN rag_documents d ON d.id = k.document_id
                   WHERE k.collection_id = ?""",
                (coll.id,),
            ).fetchall()
        return [
            SearchHit(score, row["text"], row["source"], row["title"], row["ordinal"],
                      row["document_id"])
            for score, row in _top_k(q, [tuple(r) for r in rows], k)
            for row in [dict(zip(("text", "source", "title", "ordinal", "document_id"), row))]
        ]

    # --- memoria ------------------------------------------------------------

    def add_memory(self, text: str) -> Memory:
        text = text.strip()
        if not text:
            raise RagError("La memoria está vacía.")
        if len(text) > 2000:
            raise RagError("Una memoria es un hecho corto (máx. 2000 caracteres); "
                           "para documentos usa una colección.")
        vector = _normalized(self._embedder_factory(self._memory_model)([text])[0])
        now = time.time()
        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT INTO memories (text, embedding_model, embedding, created_at) "
                "VALUES (?, ?, ?, ?)",
                (text, self._memory_model, vector.tobytes(), now),
            )
        return Memory(cur.lastrowid, text, now)

    def list_memories(self) -> list[Memory]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, text, created_at FROM memories ORDER BY id"
            ).fetchall()
        return [Memory(**dict(r)) for r in rows]

    def delete_memory(self, memory_id: int) -> bool:
        with self._lock, self._db:
            cur = self._db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0

    def search_memories(self, query: str, k: int = 3, min_score: float = 0.0) -> list[Memory]:
        if not query.strip():
            return []
        with self._lock:
            rows = self._db.execute(
                "SELECT id, text, created_at, embedding FROM memories WHERE embedding_model = ?",
                (self._memory_model,),
            ).fetchall()
        if not rows:
            return []
        q = _normalized(self._embedder_factory(self._memory_model)([query])[0])
        hits = _top_k(q, [tuple(r) for r in rows], k)
        return [Memory(row[0], row[1], row[2], score) for score, row in hits if score >= min_score]


def format_context(hits: list[SearchHit], memories: list[Memory] | None = None) -> str | None:
    """Bloque de contexto para el system prompt, con fuentes numeradas para citar."""
    parts = []
    if memories:
        parts.append("Lo que sabes del usuario (memoria):\n"
                     + "\n".join(f"- {m.text}" for m in memories))
    if hits:
        lines = [f"[{i}] ({h.title}) {h.text}" for i, h in enumerate(hits, 1)]
        parts.append("Fragmentos de los documentos del usuario. Úsalos para responder y cita "
                     "la fuente con su número entre corchetes. Si no bastan, dilo:\n"
                     + "\n\n".join(lines))
    return "\n\n".join(parts) if parts else None
