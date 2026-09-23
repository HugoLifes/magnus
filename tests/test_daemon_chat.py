"""WebSocket /chat, POST /chat, conversaciones y uso. Corren SIN GPU y SIN Ollama."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import daemon.app as app_module
from core.chat import ChatService
from core.config import Settings
from core.hardware import GPU
from core.platform import profile_for
from core.store import Store
from tests.test_chat import FakeClient


@pytest.fixture
def client(tmp_path):
    store = Store(tmp_path / "magnus.db")
    service = ChatService(
        store, Settings(), profile_for(GPU("NVIDIA GeForce RTX 4060 Laptop GPU", 8.0, 7.0)),
        FakeClient(), power_sampler=lambda: 60.0, power_interval_s=0.01,
    )
    app_module.api.dependency_overrides[app_module.get_store] = lambda: store
    app_module.api.dependency_overrides[app_module.get_chat_service] = lambda: service
    yield TestClient(app_module.api)
    app_module.api.dependency_overrides.clear()
    store.close()


def test_websocket_dos_turnos(client):
    with client.websocket_connect("/chat") as ws:
        ws.send_json({"model": "qwen2.5:1.5b", "message": "Hola"})
        events = []
        while True:
            ev = ws.receive_json()
            events.append(ev)
            if ev["type"] in ("done", "error"):
                break
        assert events[0]["type"] == "start"
        assert "".join(e["content"] for e in events if e["type"] == "token") == "Hola, soy Magnus."
        done = events[-1]
        assert done["metrics"]["tokens_out"] == 8

        ws.send_json({"model": "qwen2.5:1.5b", "message": "¿Y ahora?",
                      "conversation_id": done["conversation_id"]})
        while (ev := ws.receive_json())["type"] != "done":
            pass
        assert ev["conversation_id"] == done["conversation_id"]

    detalle = client.get(f"/conversations/{done['conversation_id']}").json()
    assert [m["role"] for m in detalle["messages"]] == ["user", "assistant", "user", "assistant"]


def test_websocket_peticion_invalida_no_cierra(client):
    with client.websocket_connect("/chat") as ws:
        ws.send_json({"sin": "modelo"})
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"model": "m", "message": "x", "conversation_id": "no-existe"})
        err = ws.receive_json()
        assert err["type"] == "error" and "no encontrada" in err["detail"]


def test_post_chat_y_uso(client):
    r = client.post("/chat", json={"model": "m", "message": "Hola"})
    assert r.status_code == 200
    assert r.json()["type"] == "done"

    uso = client.get("/usage").json()
    assert uso["turns"] == 1
    assert uso["tokens_out"] == 8
    assert uso["by_model"][0]["model"] == "m"

    lista = client.get("/conversations").json()["conversations"]
    assert len(lista) == 1
    assert client.delete(f"/conversations/{lista[0]['id']}").status_code == 200
    assert client.get(f"/conversations/{lista[0]['id']}").status_code == 404


def test_settings_put(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MAGNUS_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MAGNUS_ELECTRICITY_USD_PER_KWH", raising=False)
    r = client.put("/settings", json={"electricity_usd_per_kwh": 0.09})
    assert r.status_code == 200 and r.json()["electricity_usd_per_kwh"] == 0.09
    assert client.get("/settings").json()["electricity_usd_per_kwh"] == 0.09
    assert client.put("/settings", json={"inventado": 1}).status_code == 400
