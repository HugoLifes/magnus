"""Tests adicionales de compatibilidad: casos borde, cuant_matrix, notas."""

import pytest

from core.compatibility import (
    QUANT_PREFERENCE,
    bytes_per_param,
    estimate_kv_cache_gib,
    estimate_total_gib,
    estimate_weights_gib,
    quant_matrix,
)
from core.hardware import HARDWARE_PRESETS
from core.model_registry import get_model


def test_bytes_per_param_cuant_desconocida():
    with pytest.raises(ValueError, match="Cuantización desconocida"):
        bytes_per_param("q2")


def test_bytes_per_param_orden_descendente():
    assert bytes_per_param("fp16") > bytes_per_param("q8")
    assert bytes_per_param("q8") > bytes_per_param("q4")


def test_estimate_weights_escala_con_params():
    pequeño = estimate_weights_gib(7.0, "fp16")
    grande = estimate_weights_gib(70.0, "fp16")
    assert grande > pequeño * 9   # ~10x más


def test_kv_cache_escala_con_batch():
    spec = get_model("llama-3.1-8b")
    solo = estimate_kv_cache_gib(spec, context=8192, batch=1)
    cuatro = estimate_kv_cache_gib(spec, context=8192, batch=4)
    assert abs(cuatro - 4 * solo) < 0.01


def test_estimate_total_mayor_que_pesos():
    spec = get_model("llama-3.1-8b")
    total = estimate_total_gib(spec, "fp16", context=8192)
    pesos = estimate_weights_gib(spec.params_b, "fp16")
    assert total > pesos


def test_quant_matrix_longitud():
    spec = get_model("qwen2.5-32b")
    rows = quant_matrix(spec, HARDWARE_PRESETS["b200"])
    assert len(rows) == len(QUANT_PREFERENCE)


def test_quant_matrix_orden_decreciente_de_calidad():
    spec = get_model("llama-3.1-70b")
    rows = quant_matrix(spec, HARDWARE_PRESETS["b200"])
    quants = [r.quant for r in rows]
    assert quants == QUANT_PREFERENCE


def test_quant_matrix_fp16_entra_en_b200_para_modelos_pequeños():
    spec = get_model("llama-3.1-8b")
    rows = quant_matrix(spec, HARDWARE_PRESETS["b200"])
    fp16_row = next(r for r in rows if r.quant == "fp16")
    assert fp16_row.fits


def test_quant_matrix_405b_no_entra_fp16():
    spec = get_model("llama-3.1-405b")
    rows = quant_matrix(spec, HARDWARE_PRESETS["b200"])
    fp16_row = next(r for r in rows if r.quant == "fp16")
    assert not fp16_row.fits


def test_contexto_excedido_genera_nota():
    from core.compatibility import check_fit
    spec = get_model("mistral-7b")
    res = check_fit(spec, HARDWARE_PRESETS["b200"], quant="fp16",
                    context=spec.context_max + 1000)
    assert any("máximo" in n for n in res.notes)


def test_utilization_pct_cero_con_vram_cero():
    from core.compatibility import CompatibilityResult
    res = CompatibilityResult(
        model_id="x", quant="fp16", context=8192, batch=1,
        required_gib=10.0, available_gib=0.0,
        weights_gib=9.0, kv_cache_gib=0.5,
        fits=False, headroom_gib=-10.0,
    )
    assert res.utilization_pct == 0.0
