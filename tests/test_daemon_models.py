"""Endpoints de modelos: catálogo, locales, descarga NDJSON, carga y borrado. SIN Ollama."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import daemon.app as app_module
from core.hardware import GPU
from core.runtime_manager import LoadedModel, LocalModel, RuntimeBackend, RuntimeManagerError


class FakeManager:
    def __init__(self, fail_load=False, fail_pull=False):
        self.fail_load = fail_load
        self.fail_pull = fail_pull
        self.deleted: list[str] = []

    def ollama_available(self):
        return True

    def list_local_models(self):
        return [LocalModel("qwen2.5:1.5b", 0.92, "1.5B", "Q4_K_M", "qwen2", None)]

    def list_loaded(self):
        return []

    def serve(self, model_id, backend, pull_if_missing, force):
        if self.fail_load and not force:
            raise RuntimeManagerError("No hay memoria libre suficiente")
        return LoadedModel(model_id, RuntimeBackend.OLLAMA, 1.74, notes=["aviso"] if force else [])

    def pull(self, model_id):
        yield {"status": "pulling", "digest": "sha256:ab", "completed": 50, "total": 100,
               "percent": 50.0}
        if self.fail_pull:
            raise RuntimeManagerError("sin red")
        yield {"status": "success", "digest": None, "completed": None, "total": None,
               "percent": None}

    def delete(self, model_id):
        self.deleted.append(model_id)


@pytest.fixture
def make_client():
    def make(manager):
        app_module.api.dependency_overrides[app_module.get_runtime_manager] = lambda: manager
        return TestClient(app_module.api)

    yield make
    app_module.api.dependency_overrides.clear()


def test_catalogo_jetson(make_client, monkeypatch):
    orin = GPU("NVIDIA Jetson Orin Nano", 7.4, 2.7, unified_memory=True)
    monkeypatch.setattr(app_module, "detect_gpus", lambda: [orin])
    body = make_client(FakeManager()).get("/catalog").json()
    assert body["family"] == "jetson" and body["usable_gib"] == 2.1
    assert body["models"][0]["fits"] is True
    solo_embeddings = make_client(FakeManager()).get("/catalog?capability=embedding").json()
    assert all("embedding" in m["capabilities"] for m in solo_embeddings["models"])


def test_modelos_locales(make_client):
    body = make_client(FakeManager()).get("/models/local").json()
    assert body["models"][0]["quantization"] == "Q4_K_M"


def test_carga_negada_y_forzada(make_client):
    client = make_client(FakeManager(fail_load=True))
    r = client.post("/models/qwen3:8b/load", json={"pull_if_missing": False})
    assert r.status_code == 503 and "memoria" in r.json()["detail"]
    r = client.post("/models/qwen3:8b/load", json={"force": True})
    assert r.status_code == 200 and r.json()["notes"] == ["aviso"]
    # sin cuerpo también vale
    assert make_client(FakeManager()).post("/models/qwen2.5:1.5b/load").status_code == 200


def test_descarga_ndjson(make_client):
    with make_client(FakeManager()).stream("POST", "/models/qwen3:4b/pull") as r:
        lines = [json.loads(x) for x in r.iter_lines() if x]
    assert r.headers["content-type"].startswith("application/x-ndjson")
    assert [x["status"] for x in lines] == ["pulling", "success"]


def test_descarga_con_error_a_mitad(make_client):
    with make_client(FakeManager(fail_pull=True)).stream("POST", "/models/x/pull") as r:
        lines = [json.loads(x) for x in r.iter_lines() if x]
    assert lines[-1] == {"status": "error", "detail": "sin red"}


def test_borrar(make_client):
    manager = FakeManager()
    r = make_client(manager).delete("/models/qwen2.5:1.5b")
    assert r.status_code == 200 and manager.deleted == ["qwen2.5:1.5b"]
