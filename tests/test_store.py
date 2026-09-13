"""Conversaciones y registro del medidor en SQLite. Corren SIN GPU."""

from __future__ import annotations

import pytest

from core.store import Store, title_from


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "magnus.db")
    yield s
    s.close()


def test_conversacion_y_mensajes(store):
    conv = store.create_conversation(model="qwen2.5:1.5b", title="Hola")
    store.add_message(conv.id, "user", "¿Qué es un Jetson?")
    store.add_message(conv.id, "assistant", "Una placa de NVIDIA.", {"model": "qwen2.5:1.5b"})
    msgs = store.messages(conv.id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].metrics == {"model": "qwen2.5:1.5b"}
    assert store.get_conversation(conv.id).title == "Hola"


def test_lista_ordenada_por_actividad(store):
    a = store.create_conversation("m", "a")
    b = store.create_conversation("m", "b")
    store.add_message(a.id, "user", "mueve a arriba")
    assert [c.id for c in store.list_conversations()] == [a.id, b.id]


def test_borrar_en_cascada(store):
    conv = store.create_conversation("m", "t")
    store.add_message(conv.id, "user", "x")
    assert store.delete_conversation(conv.id) is True
    assert store.messages(conv.id) == []
    assert store.delete_conversation(conv.id) is False


def test_resumen_de_uso(store):
    conv = store.create_conversation("m", "t")
    for modelo, ahorro in (("qwen", 0.001), ("qwen", 0.002), ("llama", 0.004)):
        store.add_message(conv.id, "assistant", "r", {
            "model": modelo, "tokens_in": 100, "tokens_out": 50, "energy_wh": 0.01,
            "local_cost_usd": 0.0001, "cloud_cost_usd": ahorro + 0.0001, "savings_usd": ahorro,
        })
    resumen = store.usage_summary()
    assert resumen["turns"] == 3
    assert resumen["tokens_out"] == 150
    assert resumen["savings_usd"] == pytest.approx(0.007)
    assert [m["model"] for m in resumen["by_model"]] == ["llama", "qwen"]
    assert store.usage_summary(since=9e18)["turns"] == 0


def test_titulo():
    assert title_from("  hola   mundo ") == "hola mundo"
    assert title_from("") == "Conversación nueva"
    largo = title_from("x" * 200)
    assert len(largo) == 60 and largo.endswith("…")
