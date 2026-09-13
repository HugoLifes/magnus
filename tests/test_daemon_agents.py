"""Endpoints /agents y /tools. Corren SIN GPU y SIN Ollama."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import daemon.app as app_module
from core.agent import BUILTIN_AGENTS_DIR, AgentRegistry, AgentRunner
from core.config import Settings
from core.hardware import GPU
from core.platform import profile_for
from core.store import Store
from tests.test_agent import ScriptedClient, _answer, _tool_call


@pytest.fixture
def make_client(tmp_path):
    store = Store(tmp_path / "magnus.db")
    registry = AgentRegistry(tmp_path / "agents", BUILTIN_AGENTS_DIR)

    def make(responses):
        runner = AgentRunner(store, Settings(), profile_for(GPU("NVIDIA GeForce RTX 4090", 24, 23)),
                             ScriptedClient(responses), power_sampler=lambda: 100.0,
                             power_interval_s=0.01)
        app_module.api.dependency_overrides[app_module.get_agent_registry] = lambda: registry
        app_module.api.dependency_overrides[app_module.get_agent_runner] = lambda: runner
        return TestClient(app_module.api)

    yield make
    app_module.api.dependency_overrides.clear()
    store.close()


def _events(response):
    return [json.loads(line) for line in response.iter_lines() if line]


def test_herramientas_y_agentes_incluidos(make_client):
    client = make_client([])
    assert {t["name"] for t in client.get("/tools").json()["tools"]} >= {"calcular", "recordar"}
    nombres = {a["name"] for a in client.get("/agents").json()["agents"]}
    assert {"asistente", "investigador"} <= nombres


def test_crear_ejecutar_y_borrar(make_client):
    client = make_client([_tool_call("calcular", expresion="2+2"), _answer("Son 4.")])
    r = client.put("/agents/sumador", json={"description": "Suma.", "model": "qwen3:4b",
                                            "tools": ["calcular"]})
    assert r.status_code == 200 and r.json()["tools"] == ["calcular"]

    with client.stream("POST", "/agents/sumador/run", json={"message": "¿2+2?"}) as resp:
        events = _events(resp)
    assert [e["type"] for e in events] == ["start", "tool_call", "tool_result", "answer", "done"]
    assert events[2]["result"] == "4"
    assert events[-1]["metrics"]["tools_used"] == ["calcular"]

    assert client.delete("/agents/sumador").status_code == 200
    assert client.get("/agents/sumador").status_code == 404


def test_validaciones(make_client):
    client = make_client([])
    r = client.put("/agents/x", json={"description": "d", "tools": ["formatear_disco"]})
    assert r.status_code == 400 and "desconocidas" in r.json()["detail"]
    assert client.post("/agents/no-existe/run", json={"message": "hola"}).status_code == 404
    assert client.delete("/agents/asistente").status_code == 400  # incluido


def test_error_durante_la_ejecucion_llega_como_evento(make_client):
    client = make_client([])
    client.put("/agents/sin-modelo", json={"description": "d"})
    with client.stream("POST", "/agents/sin-modelo/run", json={"message": "hola"}) as resp:
        events = _events(resp)
    assert events == [{"type": "error", "detail": "El agente 'sin-modelo' no define modelo: indica uno."}]
