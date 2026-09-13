"""ChatService: streaming, medición y guardado. Corren SIN GPU y SIN Ollama."""

from __future__ import annotations

import pytest

from core.chat import ChatError, ChatService
from core.config import Settings
from core.hardware import GPU
from core.platform import profile_for
from core.store import Store

# Fragmentos con la forma real de /api/chat de Ollama.
_CHUNKS = [
    {"message": {"role": "assistant", "content": "Hola"}, "done": False},
    {"message": {"role": "assistant", "content": ", soy Magnus."}, "done": False},
    {"message": {"role": "assistant", "content": ""}, "done": True,
     "prompt_eval_count": 26, "eval_count": 8, "eval_duration": 400_000_000},
]


class FakeClient:
    def __init__(self, chunks=None, params=1.5):
        self.chunks = chunks if chunks is not None else _CHUNKS
        self.params = params
        self.calls: list[list[dict]] = []

    def stream_chat(self, model, messages, options=None):
        self.calls.append(list(messages))
        yield from self.chunks

    def parameter_size_b(self, model):
        return self.params


@pytest.fixture
def service_factory(tmp_path):
    store = Store(tmp_path / "magnus.db")
    orin = profile_for(GPU("NVIDIA Jetson Orin Nano", 7.4, 2.8, unified_memory=True))

    def make(client=None, settings=None):
        client = client or FakeClient()
        svc = ChatService(store, settings or Settings(), orin, client,
                          power_sampler=lambda: 7.4, power_interval_s=0.01)
        return svc, client, store

    yield make
    store.close()


def test_turno_completo(service_factory):
    svc, _, store = service_factory()
    events = list(svc.stream(model="qwen2.5:1.5b", message="Hola"))

    assert events[0]["type"] == "start"
    assert [e["content"] for e in events if e["type"] == "token"] == ["Hola", ", soy Magnus."]
    done = events[-1]
    assert done["type"] == "done"
    assert done["content"] == "Hola, soy Magnus."

    m = done["metrics"]
    assert m["tokens_in"] == 26 and m["tokens_out"] == 8
    assert m["tokens_per_s"] == 20.0          # 8 tokens en 0.4 s
    assert m["avg_power_w"] == 7.4
    assert m["cloud_reference"] == "gpt-4o-mini"  # 1.5 B → clase pequeña
    assert m["amortization_cost_usd"] >= 0

    msgs = store.messages(done["conversation_id"])
    assert [x.role for x in msgs] == ["user", "assistant"]
    assert msgs[1].metrics["tokens_out"] == 8


def test_segundo_turno_lleva_el_historial(service_factory):
    svc, client, _ = service_factory()
    first = list(svc.stream(model="m", message="Primero", system="Sé breve"))
    conv_id = first[-1]["conversation_id"]
    list(svc.stream(model="m", message="Segundo", conversation_id=conv_id, system="Sé breve"))

    enviado = client.calls[-1]
    assert enviado[0] == {"role": "system", "content": "Sé breve"}
    assert [x["content"] for x in enviado[1:]] == ["Primero", "Hola, soy Magnus.", "Segundo"]


def test_conversacion_inexistente(service_factory):
    svc, _, _ = service_factory()
    with pytest.raises(ChatError, match="no encontrada"):
        list(svc.stream(model="m", message="x", conversation_id="nope"))


def test_mensaje_vacio(service_factory):
    svc, _, _ = service_factory()
    with pytest.raises(ChatError, match="vacío"):
        list(svc.stream(model="m", message="   "))


def test_referencia_fija_y_coste_de_hardware(service_factory):
    settings = Settings(cloud_reference="claude-sonnet-4.5", hardware_cost_usd=0.0)
    svc, _, _ = service_factory(settings=settings)
    m = list(svc.stream(model="m", message="x"))[-1]["metrics"]
    assert m["cloud_reference"] == "claude-sonnet-4.5"
    assert m["amortization_cost_usd"] == 0.0
