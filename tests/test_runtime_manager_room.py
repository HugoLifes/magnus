"""Liberar modelos antes de cargar otro cuando la plataforma admite pocos. SIN GPU."""

from __future__ import annotations

import pytest

from core.hardware import GPU
from core.runtime_manager import RuntimeManager, RuntimeManagerError

GIB = 1024**3


def _orin(free):
    return GPU("NVIDIA Jetson Orin Nano", total_gib=7.4, free_gib=free, unified_memory=True)


def _mgr(monkeypatch, gpu_readings, local, running, max_loaded=None, unload_delay_polls=0):
    """`unload_delay_polls`: cuántas lecturas de /api/ps sigue apareciendo un modelo liberado."""
    readings = list(gpu_readings)
    calls: list[tuple[str, str]] = []
    sleeps: list[float] = []
    mgr = RuntimeManager(
        gpu_provider=lambda: readings.pop(0) if len(readings) > 1 else readings[0],
        reclaimer=lambda gib: None, max_loaded_models=max_loaded, sleep=sleeps.append,
    )
    o = mgr._ollama
    state = {"running": list(running), "pending": {}}
    monkeypatch.setattr(o, "is_available", lambda: True)
    monkeypatch.setattr(o, "list_local", lambda: local)

    def list_running():
        for name in list(state["pending"]):
            state["pending"][name] -= 1
            if state["pending"][name] < 0:
                state["running"] = [m for m in state["running"] if m["name"] != name]
                del state["pending"][name]
        return list(state["running"])

    def unload(name):
        calls.append(("unload", name))
        state["pending"][name] = unload_delay_polls

    monkeypatch.setattr(o, "list_running", list_running)
    monkeypatch.setattr(o, "unload_from_vram", unload)
    monkeypatch.setattr(o, "load_into_vram", lambda name: calls.append(("load", name)))
    return mgr, calls, sleeps


def test_caso_medido_jetson_embeddings_con_chat_cargado(monkeypatch):
    # Antes de liberar: 1.5 GiB libres (no cabe 1.6). Tras liberar el de chat: 2.4.
    local = [{"name": "nomic-embed-text:latest", "size": int(0.26 * GIB)}]
    running = [{"name": "qwen3:0.6b", "size_vram": int(0.87 * GIB)}]
    mgr, calls, _ = _mgr(monkeypatch, [[_orin(1.5)], [_orin(2.4)]], local, running)
    mgr.serve("nomic-embed-text", pull_if_missing=False)
    assert calls == [("unload", "qwen3:0.6b"), ("load", "nomic-embed-text")]


def test_espera_a_que_ollama_suelte_el_modelo(monkeypatch):
    local = [{"name": "nomic-embed-text:latest", "size": int(0.26 * GIB)}]
    running = [{"name": "qwen3:0.6b"}]
    # El modelo liberado sigue en /api/ps durante 3 lecturas más.
    mgr, calls, sleeps = _mgr(monkeypatch, [[_orin(1.5)], [_orin(2.4)]], local, running,
                              unload_delay_polls=3)
    mgr.serve("nomic-embed-text", pull_if_missing=False)
    assert calls[-1] == ("load", "nomic-embed-text")
    assert sleeps.count(0.3) >= 3  # esperó mientras seguía apareciendo


def test_sin_liberar_se_habria_negado(monkeypatch):
    local = [{"name": "nomic-embed-text:latest", "size": int(0.26 * GIB)}]
    running = [{"name": "qwen3:0.6b"}]
    # Límite alto: no libera nada y la guarda ve 1.5 GiB → se niega.
    mgr, calls, _ = _mgr(monkeypatch, [[_orin(1.5)]], local, running, max_loaded=3)
    with pytest.raises(RuntimeManagerError, match="memoria libre"):
        mgr.serve("nomic-embed-text", pull_if_missing=False)
    assert calls == []


def test_con_espacio_para_dos_no_libera(monkeypatch):
    rtx = GPU("NVIDIA GeForce RTX 4090", total_gib=24.0, free_gib=16.0)
    local = [{"name": "qwen3:8b", "size": int(4.8 * GIB)}]
    running = [{"name": "nomic-embed-text:latest"}]
    mgr, calls, sleeps = _mgr(monkeypatch, [[rtx]], local, running)  # 4090 → 2 modelos
    mgr.serve("qwen3:8b", pull_if_missing=False)
    assert calls == [("load", "qwen3:8b")]
    assert sleeps == []  # sin liberar, sin esperas


def test_libera_primero_el_que_antes_caduca(monkeypatch):
    local = [{"name": "c", "size": GIB}]
    running = [
        {"name": "a", "expires_at": "2026-09-13T10:00:00Z"},
        {"name": "b", "expires_at": "2026-09-13T09:00:00Z"},
    ]
    mgr, calls, _ = _mgr(monkeypatch, [[_orin(6.0)]], local, running, max_loaded=2)
    mgr.serve("c", pull_if_missing=False)
    assert calls == [("unload", "b"), ("load", "c")]


def test_modelo_ya_cargado_no_pasa_por_la_guarda(monkeypatch):
    # Caso medido: qwen3:0.6b respondía y la guarda lo rechazaba por 1.5 GiB libres.
    local = [{"name": "qwen3:0.6b", "size": GIB}]
    running = [{"name": "qwen3:0.6b", "size_vram": int(0.87 * GIB)}]
    mgr, calls, _ = _mgr(monkeypatch, [[_orin(1.5)]], local, running)
    loaded = mgr.serve("qwen3:0.6b", pull_if_missing=False)
    assert calls == []
    assert loaded.size_vram_gib == 0.87
