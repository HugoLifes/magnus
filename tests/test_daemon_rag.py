"""Endpoints /rag y /memory. Corren SIN GPU y SIN Ollama (embedder falso)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import daemon.app as app_module
from core.rag import RagStore
from tests.test_rag import fake_embedder


@pytest.fixture
def client(tmp_path):
    store = RagStore(tmp_path / "magnus.db", fake_embedder)
    app_module.api.dependency_overrides[app_module.get_rag_store] = lambda: store
    yield TestClient(app_module.api)
    app_module.api.dependency_overrides.clear()
    store.close()


def test_flujo_completo_de_coleccion(client, tmp_path):
    assert client.post("/rag/collections", json={"name": "manuales"}).status_code == 200
    assert client.post("/rag/collections", json={"name": "manuales"}).status_code == 400

    carpeta = tmp_path / "docs"
    carpeta.mkdir()
    (carpeta / "jetson.md").write_text("El Jetson Orin Nano consume entre 7 y 25 vatios.")
    r = client.post("/rag/ingest", json={
        "collection": "manuales", "paths": [str(carpeta)],
        "text": "Las tortillas llevan maíz.", "source": "receta",
    }).json()
    assert r["indexed"] == 2 and r["errors"] == {}

    hits = client.post("/rag/search", json={
        "collection": "manuales", "query": "cuántos vatios consume el jetson", "k": 1,
    }).json()["hits"]
    assert hits[0]["title"] == "jetson.md"

    docs = client.get("/rag/collections/manuales/documents").json()["documents"]
    assert len(docs) == 2
    assert client.delete(f"/rag/collections/manuales/documents/{docs[0]['id']}").status_code == 200

    lista = client.get("/rag/collections").json()["collections"]
    assert lista[0]["documents"] == 1
    assert client.delete("/rag/collections/manuales").status_code == 200
    assert client.get("/rag/collections/manuales/documents").status_code == 404


def test_ingesta_sin_nada(client):
    client.post("/rag/collections", json={"name": "x"})
    assert client.post("/rag/ingest", json={"collection": "x"}).status_code == 400
    assert client.post("/rag/ingest", json={"collection": "nope", "text": "a"}).status_code == 404


def test_memoria(client):
    mid = client.post("/memory", json={"text": "Uso un Jetson Orin Nano"}).json()["id"]
    assert client.post("/memory", json={"text": "  "}).status_code == 400
    assert client.get("/memory").json()["memories"][0]["text"] == "Uso un Jetson Orin Nano"
    hits = client.post("/memory/search", json={"query": "qué jetson uso"}).json()["memories"]
    assert hits[0]["id"] == mid and "score" in hits[0]
    assert client.delete(f"/memory/{mid}").status_code == 200
    assert client.delete(f"/memory/{mid}").status_code == 404
