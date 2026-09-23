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

    def stream_chat(self, model, messages, options=None, think=None):
        self.calls.append(list(messages))
        self.think = think
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


def test_razonamiento_va_aparte(service_factory):
    chunks = [
        {"message": {"role": "assistant", "content": "", "thinking": "Pienso..."}, "done": False},
        {"message": {"role": "assistant", "content": "Hola"}, "done": False},
        {"message": {"role": "assistant", "content": ""}, "done": True, "eval_count": 3},
    ]
    svc, _, _ = service_factory(client=FakeClient(chunks))
    events = list(svc.stream(model="qwen3:0.6b", message="hola"))
    assert [e["type"] for e in events] == ["start", "thinking", "token", "done"]
    assert events[-1]["content"] == "Hola"  # el razonamiento no se guarda como respuesta


def test_segundo_turno_lleva_el_historial(service_factory):
    svc, client, _ = service_factory()
    first = list(svc.stream(model="m", message="Primero", system="Sé breve"))
    conv_id = first[-1]["conversation_id"]
    list(svc.stream(model="m", message="Segundo", conversation_id=conv_id, system="Sé breve"))

    enviado = client.calls[-1]
    # El system del usuario se apila debajo de la identidad de Magnus.
    assert enviado[0]["role"] == "system"
    assert enviado[0]["content"].endswith("Sé breve")
    assert "Eres Magnus" in enviado[0]["content"]
    assert [x["content"] for x in enviado[1:]] == ["Primero", "Hola, soy Magnus.", "Segundo"]


def test_conversacion_inexistente(service_factory):
    svc, _, _ = service_factory()
    with pytest.raises(ChatError, match="no encontrada"):
        list(svc.stream(model="m", message="x", conversation_id="nope"))


def test_mensaje_vacio(service_factory):
    svc, _, _ = service_factory()
    with pytest.raises(ChatError, match="vacío"):
        list(svc.stream(model="m", message="   "))


def test_skill_por_invocacion_llega_como_system(service_factory, tmp_path):
    from core.skills import SkillRegistry, build_skill

    skills = SkillRegistry(tmp_path / "skills")
    skills.save(build_skill("resumir", "Resume textos.", "Resume en viñetas.", ["resume"]))
    svc, client, store = service_factory()
    svc._skills = skills

    events = list(svc.stream(model="m", message="/resumir El texto largo", system="Sé breve"))
    assert events[0]["skills"] == ["resumir"]
    enviado = client.calls[-1]
    assert enviado[0]["role"] == "system"
    contenido = enviado[0]["content"]
    assert "Sé breve" in contenido and "## Skill: resumir" in contenido
    assert contenido.index("Sé breve") < contenido.index("## Skill: resumir")
    assert enviado[-1] == {"role": "user", "content": "El texto largo"}  # sin "/resumir"
    # En la conversación queda tal como lo escribió el usuario.
    assert store.messages(events[-1]["conversation_id"])[0].content == "/resumir El texto largo"


def test_sin_skills_el_system_es_solo_la_identidad(service_factory, tmp_path):
    from core.skills import SkillRegistry

    svc, client, _ = service_factory()
    svc._skills = SkillRegistry(tmp_path / "vacio")
    events = list(svc.stream(model="m", message="hola"))
    assert events[0]["skills"] == []
    system = client.calls[-1][0]
    assert system["role"] == "system"
    assert "Eres Magnus" in system["content"]
    assert "Skill:" not in system["content"]


def test_rag_inyecta_fragmentos_con_fuentes(service_factory, tmp_path):
    from core.rag import RagStore
    from tests.test_rag import fake_embedder

    rag = RagStore(tmp_path / "rag.db", fake_embedder)
    rag.create_collection("manuales")
    rag.ingest_text("manuales", "El Jetson Orin Nano tiene 8 GB de memoria unificada.",
                    "jetson.md")
    svc, client, _ = service_factory()
    svc._rag = rag

    events = list(svc.stream(model="m", message="¿cuánta memoria tiene el jetson?",
                             collection="manuales"))
    assert events[0]["sources"][0]["title"] == "jetson.md"
    system = client.calls[-1][0]
    assert system["role"] == "system" and "[1] (jetson.md)" in system["content"]
    rag.close()


def test_rag_coleccion_inexistente_no_deja_nada_guardado(service_factory, tmp_path):
    from core.rag import RagStore
    from tests.test_rag import fake_embedder

    rag = RagStore(tmp_path / "rag.db", fake_embedder)
    svc, _, store = service_factory()
    svc._rag = rag
    with pytest.raises(ChatError, match="No existe la colección"):
        list(svc.stream(model="m", message="hola", collection="fantasma"))
    assert store.list_conversations() == []
    rag.close()


def test_memoria_automatica_segun_el_equipo(service_factory, tmp_path):
    from core.rag import RagStore
    from tests.test_rag import fake_embedder

    rag = RagStore(tmp_path / "rag.db", fake_embedder)
    rag.add_memory("El usuario trabaja con un Jetson Orin Nano")
    svc, client, _ = service_factory()  # perfil Jetson: un modelo a la vez
    svc._rag = rag

    # Pregunta con varias palabras en común: el embedder falso es bolsa de palabras.
    pregunta = "¿el usuario trabaja con un jetson orin?"
    list(svc.stream(model="m", message=pregunta))
    # En un Jetson la memoria no se usa sola: el system es solo identidad.
    assert "Jetson Orin Nano" not in client.calls[-1][0]["content"].split("Sin internet")[-1]

    list(svc.stream(model="m", message=pregunta, use_memory=True))
    assert "Jetson Orin Nano" in client.calls[-1][0]["content"]
    rag.close()


def test_referencia_fija_y_coste_de_hardware(service_factory):
    settings = Settings(cloud_reference="claude-sonnet-4.5", hardware_cost_usd=0.0)
    svc, _, _ = service_factory(settings=settings)
    m = list(svc.stream(model="m", message="x"))[-1]["metrics"]
    assert m["cloud_reference"] == "claude-sonnet-4.5"
    assert m["amortization_cost_usd"] == 0.0
