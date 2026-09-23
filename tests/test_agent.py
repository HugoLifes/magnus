"""Runtime de agentes: definición, herramientas y bucle. SIN GPU ni Ollama."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.agent import (
    BUILTIN_AGENTS_DIR,
    TOOLS,
    AgentError,
    AgentRegistry,
    AgentRunner,
    build_agent,
    parse_agent,
    render_agent,
    safe_calculate,
)
from core.chat import ChatError
from core.config import Settings
from core.hardware import GPU
from core.platform import profile_for
from core.rag import RagStore
from core.store import Store
from tests.test_rag import fake_embedder

_YAML = """
name: contador
description: Hace cuentas.
model: qwen3:4b
system: Usa la calculadora.
tools: [calcular, fecha_hora]
max_steps: 3
"""


class ScriptedClient:
    """Responde con una lista fija de respuestas de /api/chat."""

    def __init__(self, responses, params_b=4.0):
        self.responses = list(responses)
        self.params_b = params_b
        self.requests: list[tuple[list[dict], list[dict] | None]] = []
        self.think: list[bool | None] = []

    def chat_once(self, model, messages, tools=None, options=None, think=None):
        self.requests.append(([dict(m) for m in messages], tools))
        self.think.append(think)
        if not self.responses:
            return {"message": {"role": "assistant", "content": "fin"}, "eval_count": 1}
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def parameter_size_b(self, model):
        return self.params_b


def _tool_call(name, **args):
    return {"message": {"role": "assistant", "content": "",
                        "tool_calls": [{"function": {"name": name, "arguments": args}}]},
            "prompt_eval_count": 50, "eval_count": 10, "eval_duration": 100_000_000}


def _answer(text):
    return {"message": {"role": "assistant", "content": text},
            "prompt_eval_count": 80, "eval_count": 20, "eval_duration": 200_000_000}


@pytest.fixture
def runner_factory(tmp_path):
    store = Store(tmp_path / "magnus.db")
    rag = RagStore(tmp_path / "magnus.db", fake_embedder)
    platform = profile_for(GPU("NVIDIA GeForce RTX 4090", 24.0, 23.0))

    def make(client):
        return AgentRunner(store, Settings(), platform, client, power_sampler=lambda: 300.0,
                           power_interval_s=0.01, rag=rag), store, rag

    yield make
    rag.close()
    store.close()


# --- herramientas ------------------------------------------------------------


@pytest.mark.parametrize(("expr", "valor"), [
    ("(1250*0.16)+80", 280.0), ("2**10", 1024), ("7 // 2", 3), ("-3 + 5", 2), ("2^3", 8),
])
def test_calculadora_segura(expr, valor):
    assert safe_calculate(expr) == valor


@pytest.mark.parametrize("expr", [
    "__import__('os').system('rm -rf /')", "open('x')", "2**1000", "a + 1", "x" * 300,
])
def test_calculadora_rechaza_lo_peligroso(expr):
    with pytest.raises((ValueError, SyntaxError)):
        safe_calculate(expr)


def test_esquemas_de_herramientas():
    for tool in TOOLS.values():
        schema = tool.schema()
        assert schema["type"] == "function"
        assert schema["function"]["parameters"]["type"] == "object"


# --- definición ------------------------------------------------------------------


def test_parse_y_render():
    spec = parse_agent(_YAML + "think: false\n")
    assert spec.tools == ("calcular", "fecha_hora") and spec.max_steps == 3
    assert spec.think is False
    assert parse_agent(render_agent(spec)) == spec


@pytest.mark.parametrize(("cambio", "mensaje"), [
    ({"name": "Malo"}, "minúsculas"),
    ({"description": ""}, "descripción"),
    ({"tools": ["borrar_disco"]}, "Herramientas desconocidas"),
    ({"max_steps": 99}, "max_steps"),
    ({"max_steps": "muchos"}, "números"),
    ({"think": "sí"}, "true o false"),
])
def test_validacion(cambio, mensaje):
    data = {"name": "ok", "description": "d", "tools": ["calcular"]} | cambio
    with pytest.raises(AgentError, match=mensaje):
        build_agent(data)


def test_registro_usuario_pisa_incluido_y_no_se_borra_incluido(tmp_path):
    builtin, user = tmp_path / "b", tmp_path / "u"
    builtin.mkdir()
    (builtin / "contador.yaml").write_text(_YAML, encoding="utf-8")
    (builtin / "roto.yaml").write_text("name: [", encoding="utf-8")
    reg = AgentRegistry(user, builtin)
    assert reg.get("contador").source == "builtin"
    assert "roto" in reg.errors

    reg.save(build_agent({"name": "contador", "description": "mío", "tools": []}))
    assert reg.get("contador").description == "mío"
    assert reg.delete("contador") is True
    assert reg.get("contador").source == "builtin"
    with pytest.raises(AgentError, match="incluido"):
        reg.delete("contador")


def test_agentes_incluidos_son_validos():
    reg = AgentRegistry(Path("no-existe"), BUILTIN_AGENTS_DIR)
    assert reg.errors == {}
    assert {"asistente", "investigador"} <= {a.name for a in reg.list()}


# --- ejecución -------------------------------------------------------------------


def test_bucle_con_herramienta(runner_factory):
    client = ScriptedClient([_tool_call("calcular", expresion="(1250*0.16)+80"),
                             _answer("Son 280 pesos.")])
    runner, store, _ = runner_factory(client)
    spec = parse_agent(_YAML)

    events = list(runner.run(spec, "¿Cuánto es 1250 más IVA más 80?"))
    tipos = [e["type"] for e in events]
    assert tipos == ["start", "tool_call", "tool_result", "answer", "done"]
    assert events[0]["notes"] == []
    assert events[2]["result"] == "280.0"

    # El resultado de la herramienta vuelve al modelo en el segundo paso.
    segundo = client.requests[1][0]
    assert segundo[-1] == {"role": "tool", "content": "280.0", "tool_name": "calcular"}
    assert client.requests[0][1][0]["function"]["name"] == "calcular"

    done = events[-1]
    m = done["metrics"]
    assert m["steps"] == 2 and m["tools_used"] == ["calcular"]
    assert m["tokens_in"] == 130 and m["tokens_out"] == 30
    assert m["agent"] == "contador" and m["avg_power_w"] == 300.0
    assert store.get_conversation(done["conversation_id"]).model == "agente:contador"


def test_think_del_agente_llega_a_ollama(runner_factory):
    client = ScriptedClient([_answer("ok")])
    runner, _, _ = runner_factory(client)
    list(runner.run(parse_agent(_YAML + "think: false\n"), "hola"))
    assert client.think == [False]


def test_aviso_con_modelo_pequeno(runner_factory):
    client = ScriptedClient([_answer("1890.22")], params_b=0.6)
    runner, _, _ = runner_factory(client)
    start = next(runner.run(parse_agent(_YAML), "cuenta"))
    assert "4 B o más" in start["notes"][0]


def test_herramienta_no_permitida_y_error_se_devuelven_al_modelo(runner_factory):
    client = ScriptedClient([
        _tool_call("recordar", hecho="x"),            # no está en tools del agente
        _tool_call("calcular", expresion="1/0"),       # error de la herramienta
        _answer("No se puede dividir entre cero."),
    ])
    runner, _, _ = runner_factory(client)
    events = list(runner.run(parse_agent(_YAML), "divide"))
    resultados = [e["result"] for e in events if e["type"] == "tool_result"]
    assert "no permitida" in resultados[0]
    assert resultados[1].startswith("Error al usar calcular")
    assert events[-1]["content"] == "No se puede dividir entre cero."


def test_limite_de_pasos(runner_factory):
    client = ScriptedClient([_tool_call("fecha_hora") for _ in range(5)])
    runner, _, _ = runner_factory(client)
    done = list(runner.run(parse_agent(_YAML), "hora"))[-1]
    assert done["metrics"]["stop_reason"] == "límite de pasos"
    assert done["metrics"]["steps"] == 3


def test_busqueda_de_documentos_y_memoria(runner_factory):
    client = ScriptedClient([_tool_call("buscar_documentos", consulta="memoria jetson"),
                             _tool_call("recordar", hecho="Le interesa el Jetson"),
                             _answer("Tiene 8 GB [1].")])
    runner, _, rag = runner_factory(client)
    rag.create_collection("documentos")
    rag.ingest_text("documentos", "El Jetson Orin Nano tiene 8 GB de memoria.", "jetson.md")
    spec = build_agent({"name": "inv", "description": "d", "model": "m",
                        "tools": ["buscar_documentos", "recordar"], "collection": "documentos"})

    events = list(runner.run(spec, "¿cuánta memoria tiene el jetson?"))
    resultados = [e["result"] for e in events if e["type"] == "tool_result"]
    assert "[1] (jetson.md)" in resultados[0]
    assert "Guardado" in resultados[1]
    assert rag.list_memories()[0].text == "Le interesa el Jetson"


def test_errores_de_ejecucion(runner_factory):
    client = ScriptedClient([ChatError("El modelo m no soporta herramientas.")])
    runner, _, _ = runner_factory(client)
    sin_modelo = build_agent({"name": "x", "description": "d"})
    with pytest.raises(AgentError, match="no define modelo"):
        list(runner.run(sin_modelo, "hola"))
    with pytest.raises(AgentError, match="no soporta herramientas"):
        list(runner.run(parse_agent(_YAML), "hola"))
    with pytest.raises(AgentError, match="no encontrada"):
        list(runner.run(parse_agent(_YAML), "hola", conversation_id="nope"))
