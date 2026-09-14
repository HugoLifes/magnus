"""Rutas /providers y chat con proveedor. Sin red: el cliente remoto es falso."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import daemon.app as app_module
from core.chat import ChatService
from core.config import Settings
from core.hardware import GPU
from core.platform import profile_for
from core.providers import ProviderError, ProviderRegistry
from core.secrets import SecretStore
from core.store import Store
from tests.test_chat import FakeClient


class FakeRegistry(ProviderRegistry):
    """Registro real en disco, con un cliente remoto falso."""

    def __init__(self, directory, fail: bool = False):
        super().__init__(directory, SecretStore(directory, use_keyring=False))
        self.fail = fail
        self.remote = FakeClient(params=70)
        self.remote.list_models = self._models

    def _models(self):
        if self.fail:
            raise ProviderError("La clave de NVIDIA API no es válida o no tiene permiso.")
        return ["meta/llama-3.3-70b-instruct", "nvidia/nemotron-mini-4b-instruct"]

    def client(self, provider_id):
        _, provider = super().client(provider_id)
        return self.remote, provider


@pytest.fixture
def ctx(tmp_path):
    registry = FakeRegistry(tmp_path)
    store = Store(tmp_path / "magnus.db")
    service = ChatService(
        store, Settings(), profile_for(GPU("NVIDIA GeForce RTX 5080 Laptop GPU", 16.0, 15.0)),
        FakeClient(), power_sampler=lambda: 90.0, power_interval_s=0.01,
        remote=registry.client,
    )
    overrides = app_module.api.dependency_overrides
    overrides[app_module.get_provider_registry] = lambda: registry
    overrides[app_module.get_store] = lambda: store
    overrides[app_module.get_chat_service] = lambda: service
    yield TestClient(app_module.api), registry
    overrides.clear()
    store.close()


def test_presets_incluyen_aviso_de_nvidia(ctx):
    client, _ = ctx
    body = client.get("/providers").json()
    nvidia = next(p for p in body["presets"] if p["kind"] == "nvidia")
    assert "producción" in nvidia["notice"] and nvidia["needs_key"] is True
    assert body["providers"] == []


def test_alta_con_clave_que_nunca_vuelve(ctx):
    client, registry = ctx
    r = client.put("/providers/nvidia", json={"kind": "nvidia", "api_key": "nvapi-123"})
    assert r.status_code == 200
    data = r.json()
    assert data["has_key"] is True and data["location"] == "cloud"
    assert "nvapi-123" not in r.text
    assert "nvapi-123" not in client.get("/providers").text
    assert registry.has_key("nvidia")


def test_errores_de_alta(ctx):
    client, _ = ctx
    assert client.put("/providers/x", json={"kind": "inventado"}).status_code == 400
    r = client.put("/providers/nvidia", json={"kind": "nvidia"})
    assert r.status_code == 400 and "clave" in r.json()["detail"]


def test_probar_y_listar_modelos(ctx):
    client, registry = ctx
    client.put("/providers/spark", json={"kind": "vllm", "base_url": "http://192.168.1.40:8000/v1"})
    ok = client.post("/providers/spark/test").json()
    assert ok == {"ok": True, "location": "lan", "models": 2,
                  "sample": ["meta/llama-3.3-70b-instruct", "nvidia/nemotron-mini-4b-instruct"]}
    assert len(client.get("/providers/spark/models").json()["models"]) == 2

    registry.fail = True
    fail = client.post("/providers/spark/test").json()
    assert fail["ok"] is False and "clave" in fail["detail"]


def test_borrar(ctx):
    client, _ = ctx
    client.put("/providers/nvidia", json={"kind": "nvidia", "api_key": "k"})
    assert client.delete("/providers/nvidia").status_code == 200
    assert client.delete("/providers/nvidia").status_code == 404


def test_chat_por_proveedor(ctx):
    client, _ = ctx
    client.put("/providers/spark", json={"kind": "vllm", "base_url": "http://192.168.1.40:8000/v1"})
    done = client.post("/chat", json={"model": "llama-3.3-70b", "message": "Hola",
                                      "provider": "spark"}).json()
    assert done["metrics"]["provider"] == "spark"
    assert done["metrics"]["location"] == "lan"
    assert done["metrics"]["avg_power_w"] is None

    local = client.post("/chat", json={"model": "qwen2.5:1.5b", "message": "Hola"}).json()
    assert local["metrics"]["location"] == "local"
