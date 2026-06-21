"""Tests del RuntimeManager. Corren SIN GPU y SIN Ollama (usan monkeypatch)."""

from __future__ import annotations

import pytest

from core.runtime_manager import (
    RuntimeBackend,
    RuntimeManager,
    RuntimeManagerError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mgr():
    return RuntimeManager(ollama_url="http://127.0.0.1:11434")


def _patch_ollama(monkeypatch, mgr, *, available=True, local=None, running=None):
    """Inyecta respuestas ficticias en el OllamaClient del manager."""
    monkeypatch.setattr(mgr._ollama, "is_available", lambda: available)
    monkeypatch.setattr(mgr._ollama, "list_local", lambda: local or [])
    monkeypatch.setattr(mgr._ollama, "list_running", lambda: running or [])
    monkeypatch.setattr(mgr._ollama, "pull", lambda model_id: None)
    monkeypatch.setattr(mgr._ollama, "load_into_vram", lambda model_id: None)
    monkeypatch.setattr(mgr._ollama, "unload_from_vram", lambda model_id: None)
    monkeypatch.setattr(mgr._ollama, "delete", lambda model_id: None)


# ---------------------------------------------------------------------------
# serve()
# ---------------------------------------------------------------------------

def test_serve_carga_modelo_existente(monkeypatch, mgr):
    local_models = [{"name": "llama3.1:8b"}]
    running_models = [{"name": "llama3.1:8b", "size_vram": 5 * 1024**3}]
    _patch_ollama(monkeypatch, mgr, local=local_models, running=running_models)

    loaded = mgr.serve("llama3.1:8b")

    assert loaded.model_id == "llama3.1:8b"
    assert loaded.backend == RuntimeBackend.OLLAMA
    assert loaded.size_vram_gib == 5.0


def test_serve_descarga_si_no_existe_localmente(monkeypatch, mgr):
    pulled = []
    _patch_ollama(monkeypatch, mgr, local=[])
    monkeypatch.setattr(mgr._ollama, "pull", lambda m: pulled.append(m))

    mgr.serve("llama3.1:8b", pull_if_missing=True)

    assert "llama3.1:8b" in pulled


def test_serve_no_descarga_con_pull_if_missing_false(monkeypatch, mgr):
    pulled = []
    _patch_ollama(monkeypatch, mgr, local=[])
    monkeypatch.setattr(mgr._ollama, "pull", lambda m: pulled.append(m))

    mgr.serve("llama3.1:8b", pull_if_missing=False)

    assert pulled == []


def test_serve_falla_si_ollama_no_disponible(monkeypatch, mgr):
    _patch_ollama(monkeypatch, mgr, available=False)

    with pytest.raises(RuntimeManagerError, match="Ollama no está disponible"):
        mgr.serve("llama3.1:8b")


def test_serve_backend_no_soportado(monkeypatch, mgr):
    _patch_ollama(monkeypatch, mgr)

    with pytest.raises(RuntimeManagerError, match="no implementado"):
        mgr.serve("llama3.1:8b", backend=RuntimeBackend.VLLM)


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

def test_stop_libera_vram(monkeypatch, mgr):
    unloaded = []
    _patch_ollama(monkeypatch, mgr)
    monkeypatch.setattr(mgr._ollama, "unload_from_vram", lambda m: unloaded.append(m))

    mgr.stop("llama3.1:8b")

    assert "llama3.1:8b" in unloaded


def test_stop_con_delete_local_borra_disco(monkeypatch, mgr):
    deleted = []
    _patch_ollama(monkeypatch, mgr)
    monkeypatch.setattr(mgr._ollama, "delete", lambda m: deleted.append(m))

    mgr.stop("llama3.1:8b", delete_local=True)

    assert "llama3.1:8b" in deleted


def test_stop_sin_delete_no_borra_disco(monkeypatch, mgr):
    deleted = []
    _patch_ollama(monkeypatch, mgr)
    monkeypatch.setattr(mgr._ollama, "delete", lambda m: deleted.append(m))

    mgr.stop("llama3.1:8b", delete_local=False)

    assert deleted == []


def test_stop_falla_si_ollama_no_disponible(monkeypatch, mgr):
    _patch_ollama(monkeypatch, mgr, available=False)

    with pytest.raises(RuntimeManagerError):
        mgr.stop("llama3.1:8b")


# ---------------------------------------------------------------------------
# list_loaded()
# ---------------------------------------------------------------------------

def test_list_loaded_vacio(monkeypatch, mgr):
    _patch_ollama(monkeypatch, mgr, running=[])
    assert mgr.list_loaded() == []


def test_list_loaded_devuelve_modelos(monkeypatch, mgr):
    running = [
        {"name": "llama3.1:8b", "size_vram": 4 * 1024**3},
        {"name": "qwen2.5:7b", "size_vram": 0},
    ]
    _patch_ollama(monkeypatch, mgr, running=running)

    result = mgr.list_loaded()

    assert len(result) == 2
    assert result[0].model_id == "llama3.1:8b"
    assert result[0].size_vram_gib == 4.0
    assert result[1].model_id == "qwen2.5:7b"


def test_list_loaded_sin_ollama_devuelve_vacio(monkeypatch, mgr):
    _patch_ollama(monkeypatch, mgr, available=False)
    assert mgr.list_loaded() == []


# ---------------------------------------------------------------------------
# list_available() y _model_exists_locally()
# ---------------------------------------------------------------------------

def test_list_available(monkeypatch, mgr):
    _patch_ollama(monkeypatch, mgr, local=[{"name": "llama3.1:8b"}, {"name": "qwen2.5:7b"}])
    result = mgr.list_available()
    assert "llama3.1:8b" in result
    assert "qwen2.5:7b" in result


def test_model_exists_locally_con_tag(monkeypatch, mgr):
    _patch_ollama(monkeypatch, mgr, local=[{"name": "llama3.1:8b"}])
    assert mgr._model_exists_locally("llama3.1:8b")


def test_model_exists_locally_sin_tag_normaliza(monkeypatch, mgr):
    # Ollama añade ":latest" — el manager debe resolverlo
    _patch_ollama(monkeypatch, mgr, local=[{"name": "llama3.1:latest"}])
    assert mgr._model_exists_locally("llama3.1")


def test_model_no_existe_localmente(monkeypatch, mgr):
    _patch_ollama(monkeypatch, mgr, local=[])
    assert not mgr._model_exists_locally("modelo-que-no-existe")


# ---------------------------------------------------------------------------
# RuntimeManagerError
# ---------------------------------------------------------------------------

def test_runtime_manager_error_str():
    err = RuntimeManagerError("algo falló")
    assert str(err) == "algo falló"
