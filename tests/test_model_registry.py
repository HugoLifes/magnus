"""Tests del registro de modelos. Corren SIN GPU."""

import pytest

from core.model_registry import MODEL_REGISTRY, ModelSpec, get_model


def test_get_model_conocido():
    spec = get_model("llama-3.1-8b")
    assert isinstance(spec, ModelSpec)
    assert spec.params_b == 8.03
    assert spec.architecture == "llama"


def test_get_model_desconocido_lanza_keyerror():
    with pytest.raises(KeyError, match="Modelo desconocido"):
        get_model("modelo-inventado")


def test_head_dim_calculado():
    spec = get_model("llama-3.1-70b")
    assert spec.head_dim == spec.hidden // spec.n_heads


def test_todos_tienen_campos_obligatorios():
    for model_id, spec in MODEL_REGISTRY.items():
        assert spec.params_b > 0, f"{model_id}: params_b debe ser positivo"
        assert spec.n_layers > 0, f"{model_id}: n_layers debe ser positivo"
        assert spec.hidden > 0, f"{model_id}: hidden debe ser positivo"
        assert spec.n_heads > 0, f"{model_id}: n_heads debe ser positivo"
        assert spec.n_kv_heads > 0, f"{model_id}: n_kv_heads debe ser positivo"
        assert spec.context_max > 0, f"{model_id}: context_max debe ser positivo"
        assert spec.n_kv_heads <= spec.n_heads, f"{model_id}: n_kv_heads > n_heads"


def test_gqa_llama_3():
    spec = get_model("llama-3.1-70b")
    assert spec.n_kv_heads < spec.n_heads  # usa GQA


def test_modelos_registrados_minimo():
    assert len(MODEL_REGISTRY) >= 5
