"""Descarga con progreso, guarda de memoria y modelos locales. SIN GPU ni Ollama."""

from __future__ import annotations

import pytest

from core.hardware import GPU
from core.runtime_manager import RuntimeManager, RuntimeManagerError, friendly_ollama_error

GIB = 1024**3
ORIN = GPU("NVIDIA Jetson Orin Nano", total_gib=7.4, free_gib=2.7, unified_memory=True)
GTX1650 = GPU("NVIDIA GeForce GTX 1650", total_gib=4.0, free_gib=3.9)


def _mgr(monkeypatch, gpus, local, running=None):
    reclaimed: list[float] = []
    mgr = RuntimeManager(gpu_provider=gpus.copy,
                         reclaimer=lambda gib: reclaimed.append(gib) or 9.9)
    o = mgr._ollama
    loaded: list[str] = []
    monkeypatch.setattr(o, "is_available", lambda: True)
    monkeypatch.setattr(o, "list_local", lambda: local)
    monkeypatch.setattr(o, "list_running", lambda: running or [])
    monkeypatch.setattr(o, "pull", lambda m: None)
    monkeypatch.setattr(o, "load_into_vram", loaded.append)
    return mgr, loaded, reclaimed


def test_jetson_se_niega_a_cargar_lo_que_no_cabe(monkeypatch):
    local = [{"name": "llama3.1:8b", "size": int(4.6 * GIB)}]
    mgr, loaded, reclaimed = _mgr(monkeypatch, [ORIN], local)
    with pytest.raises(RuntimeManagerError, match="colgar el equipo"):
        mgr.serve("llama3.1:8b")
    assert loaded == [] and reclaimed == []  # ni liberó caché ni pidió cargar


def test_jetson_force_carga_igual(monkeypatch):
    local = [{"name": "llama3.1:8b", "size": int(4.6 * GIB)}]
    mgr, loaded, _ = _mgr(monkeypatch, [ORIN], local)
    mgr.serve("llama3.1:8b", force=True)
    assert loaded == ["llama3.1:8b"]


def test_jetson_libera_cache_antes_de_cargar(monkeypatch):
    local = [{"name": "qwen2.5:1.5b", "size": 986 * 1024**2}]
    mgr, loaded, reclaimed = _mgr(monkeypatch, [ORIN], local)
    result = mgr.serve("qwen2.5:1.5b")
    assert reclaimed == [1.9]  # 0.96 GiB × 1.2 + 0.7
    assert loaded == ["qwen2.5:1.5b"] and result.notes == []


def test_gpu_dedicada_no_libera_cache_y_avisa(monkeypatch):
    local = [{"name": "qwen3:14b", "size": int(8.7 * GIB)}]
    mgr, loaded, reclaimed = _mgr(monkeypatch, [GTX1650], local)
    result = mgr.serve("qwen3:14b")
    assert loaded == ["qwen3:14b"] and reclaimed == []
    assert "CPU" in result.notes[0]


_OOM = RuntimeManagerError(
    'Ollama respondió 500: {"error":"llama runner process has terminated: '
    'cudaMalloc failed: out of memory"}'
)


def test_jetson_reintenta_una_vez_si_cuda_se_queda_sin_memoria(monkeypatch):
    local = [{"name": "qwen2.5:1.5b", "size": GIB}]
    mgr, _, reclaimed = _mgr(monkeypatch, [ORIN], local)
    intentos = []

    def load(model_id):
        intentos.append(model_id)
        if len(intentos) == 1:
            raise _OOM

    monkeypatch.setattr(mgr._ollama, "load_into_vram", load)
    mgr.serve("qwen2.5:1.5b")
    assert len(intentos) == 2
    assert reclaimed[-1] == float("inf")  # el segundo intento desaloja todo


def test_jetson_dos_fallos_de_memoria_dan_mensaje_util(monkeypatch):
    local = [{"name": "qwen2.5:1.5b", "size": GIB}]
    mgr, _, _ = _mgr(monkeypatch, [ORIN], local)

    def load(model_id):
        raise _OOM

    monkeypatch.setattr(mgr._ollama, "load_into_vram", load)
    with pytest.raises(RuntimeManagerError, match="Cierra aplicaciones"):
        mgr.serve("qwen2.5:1.5b")


def test_error_que_no_es_de_memoria_no_reintenta(monkeypatch):
    local = [{"name": "qwen2.5:1.5b", "size": GIB}]
    mgr, _, reclaimed = _mgr(monkeypatch, [ORIN], local)
    intentos = []

    def load(model_id):
        intentos.append(model_id)
        raise RuntimeManagerError("Ollama respondió 404: model not found")

    monkeypatch.setattr(mgr._ollama, "load_into_vram", load)
    with pytest.raises(RuntimeManagerError, match="404"):
        mgr.serve("qwen2.5:1.5b")
    assert len(intentos) == 1 and float("inf") not in reclaimed


def test_gpu_dedicada_no_reintenta(monkeypatch):
    local = [{"name": "qwen3:14b", "size": int(8.7 * GIB)}]
    mgr, _, _ = _mgr(monkeypatch, [GTX1650], local)
    monkeypatch.setattr(mgr._ollama, "load_into_vram", lambda m: (_ for _ in ()).throw(_OOM))
    with pytest.raises(RuntimeManagerError, match="out of memory"):
        mgr.serve("qwen3:14b")


def test_ensure_loaded_no_recarga_si_ya_esta(monkeypatch):
    local = [{"name": "qwen2.5:1.5b", "size": GIB}]
    mgr, loaded, _ = _mgr(monkeypatch, [ORIN], local, running=[{"name": "qwen2.5:1.5b"}])
    assert mgr.ensure_loaded("qwen2.5:1.5b") is None
    assert loaded == []


def test_ensure_loaded_recarga_con_guarda(monkeypatch):
    local = [{"name": "qwen2.5:1.5b", "size": GIB}]
    mgr, loaded, reclaimed = _mgr(monkeypatch, [ORIN], local)
    assert mgr.ensure_loaded("qwen2.5:1.5b") is not None
    assert loaded == ["qwen2.5:1.5b"] and reclaimed


def test_ensure_loaded_modelo_no_descargado(monkeypatch):
    mgr, _, _ = _mgr(monkeypatch, [ORIN], [])
    with pytest.raises(RuntimeManagerError, match="magnus fetch qwen3:4b"):
        mgr.ensure_loaded("qwen3:4b")


def test_progreso_normalizado(monkeypatch):
    mgr, _, _ = _mgr(monkeypatch, [], [])
    eventos = [
        {"status": "pulling manifest"},
        {"status": "pulling 65ec", "digest": "sha256:65ec", "total": 1000, "completed": 250},
        {"status": "pulling 65ec", "digest": "sha256:65ec", "total": 1000, "completed": 1000},
        {"status": "success"},
    ]
    monkeypatch.setattr(mgr._ollama, "pull_stream", lambda m: iter(eventos))
    progreso = list(mgr.pull("qwen2.5:1.5b"))
    assert [p["percent"] for p in progreso] == [None, 25.0, 100.0, None]
    assert progreso[-1]["status"] == "success"


def test_progreso_sin_ollama(monkeypatch):
    mgr = RuntimeManager(gpu_provider=list, reclaimer=None)
    monkeypatch.setattr(mgr._ollama, "is_available", lambda: False)
    with pytest.raises(RuntimeManagerError, match="no está disponible"):
        list(mgr.pull("x"))


def test_error_de_ollama_viejo_es_accionable():
    # Mensaje real del registro con Ollama 0.6.5 al pedir qwen3.
    real = ("pull model manifest: 412: \nThe model you are attempting to pull requires a "
            "newer version of Ollama.\n\nPlease download the latest version at:\n")
    assert "versión de Ollama más nueva" in friendly_ollama_error(real)
    assert friendly_ollama_error("model not found ") == "Ollama: model not found"


def test_version_de_ollama(monkeypatch):
    mgr, _, _ = _mgr(monkeypatch, [], [])
    monkeypatch.setattr(mgr._ollama, "_get", lambda path: {"version": "0.6.5"})
    assert mgr.ollama_version() == "0.6.5"
    monkeypatch.setattr(mgr._ollama, "is_available", lambda: False)
    assert mgr.ollama_version() is None


def test_modelos_locales_con_detalles(monkeypatch):
    local = [{
        "name": "qwen2.5:1.5b", "size": 986_000_000, "modified_at": "2026-09-13T07:50:00Z",
        "details": {"parameter_size": "1.5B", "quantization_level": "Q4_K_M", "family": "qwen2"},
    }]
    mgr, _, _ = _mgr(monkeypatch, [], local)
    [m] = mgr.list_local_models()
    assert m.model_id == "qwen2.5:1.5b"
    assert m.size_gib == 0.92
    assert m.quantization == "Q4_K_M"
    assert m.to_dict()["parameter_size"] == "1.5B"
