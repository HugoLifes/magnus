"""Chat en un proveedor remoto: no carga modelos locales y mide lo que cobró."""

from __future__ import annotations

import pytest

from core.chat import ChatError, ChatService
from core.config import Settings
from core.hardware import GPU
from core.platform import profile_for
from core.providers import Provider, ProviderKind
from core.store import Store
from tests.test_chat import FakeClient

_REMOTE_CHUNKS = [
    {"message": {"content": "Respuesta"}, "done": False},
    {"message": {"content": " remota"}, "done": False},
    {"message": {"content": ""}, "done": True, "prompt_eval_count": 1000,
     "eval_count": 500, "eval_duration": 250_000_000},
]


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path / "magnus.db")
    loaded: list[str] = []
    remote_client = FakeClient(_REMOTE_CHUNKS, params=70)
    cloud = Provider("magnus-cloud", ProviderKind.MAGNUS_CLOUD, "Magnus Cloud",
                     "https://cloud.example/v1", input_usd_per_mtok=0.2,
                     output_usd_per_mtok=0.6)
    lan = Provider("spark", ProviderKind.VLLM, "DGX Spark", "http://192.168.1.40:8000/v1")
    providers = {"magnus-cloud": cloud, "spark": lan}

    def remote(pid):
        if pid not in providers:
            raise ChatError(f"No hay un proveedor configurado con id '{pid}'.")
        return remote_client, providers[pid]

    orin = profile_for(GPU("NVIDIA Jetson Orin Nano", 7.4, 2.8, unified_memory=True))
    svc = ChatService(store, Settings(), orin, FakeClient(), power_sampler=lambda: 7.4,
                      power_interval_s=0.01, ensure_loaded=loaded.append, remote=remote)
    yield svc, loaded, store
    store.close()


def test_turno_en_la_nube(setup):
    svc, loaded, store = setup
    events = list(svc.stream(model="qwen3-32b", message="Hola", provider="magnus-cloud"))

    assert loaded == []  # nada que cargar en el Jetson
    assert events[0]["provider"] == "magnus-cloud" and events[0]["location"] == "cloud"
    m = events[-1]["metrics"]
    assert m["provider"] == "magnus-cloud" and m["location"] == "cloud"
    assert m["avg_power_w"] is None and m["local_cost_usd"] == 0
    assert m["provider_cost_usd"] == pytest.approx(0.0005)  # 1000×0.2 + 500×0.6 por millón
    assert m["savings_usd"] == pytest.approx(m["cloud_cost_usd"] - 0.0005)
    assert m["cloud_reference"] == "gpt-5"  # 70 B → clase grande
    assert store.messages(events[-1]["conversation_id"])[1].metrics["location"] == "cloud"


def test_vllm_en_la_red(setup):
    svc, _, _ = setup
    done = list(svc.stream(model="qwen3-32b", message="Hola", provider="spark"))[-1]
    assert done["metrics"]["location"] == "lan"
    assert done["metrics"]["provider_cost_usd"] is None


def test_local_sigue_igual(setup):
    svc, loaded, _ = setup
    events = list(svc.stream(model="qwen2.5:1.5b", message="Hola"))
    assert loaded == ["qwen2.5:1.5b"]
    assert events[0]["provider"] == "local"
    m = events[-1]["metrics"]
    assert m["location"] == "local" and m["avg_power_w"] == 7.4


def test_proveedor_desconocido_no_deja_basura(setup):
    svc, _, store = setup
    with pytest.raises(ChatError, match="No hay un proveedor"):
        list(svc.stream(model="m", message="Hola", provider="no-existe"))
    assert store.list_conversations() == []
