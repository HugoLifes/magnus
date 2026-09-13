"""Memoria y mini-RAG local. Corren SIN GPU y SIN Ollama (embedder falso)."""

from __future__ import annotations

import hashlib
import re

import pytest

from core import rag
from core.rag import (
    RagError,
    RagStore,
    SearchHit,
    chunk_text,
    extract_text,
    format_context,
)


def fake_embedder(model: str):
    """Bolsa de palabras con hashing: textos con palabras en común se parecen."""
    def embed(texts):
        vectors = []
        for text in texts:
            vec = [0.0] * 64
            for word in re.findall(r"\w+", text.lower()):
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1.0
            vectors.append(vec)
        return vectors
    embed.model = model
    return embed


@pytest.fixture
def store(tmp_path):
    s = RagStore(tmp_path / "magnus.db", fake_embedder)
    yield s
    s.close()


def test_chunking_respeta_tamano_y_solapa():
    parrafos = [f"Párrafo {i}. " + "palabra " * 40 for i in range(10)]
    chunks = chunk_text("\n\n".join(parrafos), chunk_chars=500, overlap_chars=80)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # El inicio de un fragmento repite el final del anterior.
    assert chunks[1].split()[0] in chunks[0]


def test_chunking_parrafo_gigante_y_vacio():
    assert all(len(c) <= 200 for c in chunk_text("x" * 1000, chunk_chars=200))
    assert chunk_text("   \n\n  ") == []
    with pytest.raises(RagError):
        chunk_text("hola", chunk_chars=0)


def test_extraer_html_y_no_soportado(tmp_path):
    page = tmp_path / "a.html"
    page.write_text("<html><style>x{}</style><body><p>Hola &amp; adiós</p></body></html>",
                    encoding="utf-8")
    assert "Hola & adiós" in extract_text(page)
    raro = tmp_path / "a.exe"
    raro.write_bytes(b"MZ")
    with pytest.raises(RagError, match="no soportado"):
        extract_text(raro)


def test_coleccion_ingesta_y_busqueda(store, tmp_path):
    store.create_collection("manuales", chunk_chars=300, overlap_chars=30)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "jetson.md").write_text("El Jetson Orin Nano tiene memoria unificada de 8 GB.\n\n"
                                    "Consume entre 7 y 25 vatios según el modo de energía.")
    (docs / "cocina.txt").write_text("La receta de tortillas lleva maíz, agua y cal.")
    (docs / ".oculto.md").write_text("no debe indexarse")
    (docs / "foto.png").write_bytes(b"\x89PNG")

    res = store.ingest_path("manuales", docs)
    assert res["indexed"] == 2 and res["errors"] == {}

    hits = store.search("manuales", "cuánta memoria tiene el jetson", k=2)
    assert hits[0].title == "jetson.md"
    assert hits[0].score >= hits[1].score

    coll = store.get_collection("manuales")
    assert coll.documents == 2 and coll.chunks >= 2


def test_reindexar_el_mismo_contenido_no_duplica(store):
    store.create_collection("notas")
    assert store.ingest_text("notas", "Un texto.", "a.txt")["skipped"] is False
    assert store.ingest_text("notas", "Un texto.", "copia.txt")["skipped"] is True
    assert store.get_collection("notas").documents == 1


def test_errores_de_coleccion(store):
    store.create_collection("x")
    with pytest.raises(RagError, match="Ya existe"):
        store.create_collection("x")
    with pytest.raises(RagError, match="No existe"):
        store.search("nada", "hola")
    with pytest.raises(RagError):
        store.create_collection("   ")
    with pytest.raises(RagError, match="no tiene texto"):
        store.ingest_text("x", "  ", "vacio.txt")


def test_borrar_documento_y_coleccion(store):
    store.create_collection("tmp")
    doc = store.ingest_text("tmp", "algo que borrar", "a.txt")["document_id"]
    assert store.list_documents("tmp")[0]["id"] == doc
    assert store.delete_document("tmp", doc) is True
    assert store.get_collection("tmp").chunks == 0
    store.delete_collection("tmp")
    assert store.list_collections() == []


def test_memoria(store):
    store.add_memory("Mi nombre es Hugo y entreno modelos de IA")
    store.add_memory("Tengo un Jetson Orin Nano en la oficina")
    hits = store.search_memories("¿qué equipo jetson tengo?", k=1)
    assert "Jetson" in hits[0].text and hits[0].score > 0
    assert len(store.list_memories()) == 2
    assert store.delete_memory(hits[0].id) is True
    with pytest.raises(RagError, match="vacía"):
        store.add_memory("  ")
    with pytest.raises(RagError, match="hecho corto"):
        store.add_memory("x" * 3000)


def test_busqueda_sin_numpy_da_lo_mismo(store, monkeypatch):
    store.create_collection("c")
    store.ingest_text("c", "gatos y perros\n\nautos y trenes", "a.txt")
    con = [h.text for h in store.search("c", "perros", k=1)]
    monkeypatch.setattr(rag, "_np", None)
    sin = [h.text for h in store.search("c", "perros", k=1)]
    assert con == sin


def test_contexto_con_citas():
    hits = [SearchHit(0.9, "El Orin tiene 8 GB.", "/d/jetson.md", "jetson.md", 0, "d1")]
    ctx = format_context(hits, [rag.Memory(1, "Se llama Hugo", 0.0)])
    assert "[1] (jetson.md) El Orin tiene 8 GB." in ctx
    assert "- Se llama Hugo" in ctx
    assert format_context([]) is None
