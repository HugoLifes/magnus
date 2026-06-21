"""Tests del cálculo de compatibilidad. Corren SIN GPU (usan presets)."""

from core import check_fit, get_model, recommend_quant
from core.hardware import HARDWARE_PRESETS


def test_8b_entra_sobrado_en_b200():
    spec = get_model("llama-3.1-8b")
    res = check_fit(spec, HARDWARE_PRESETS["b200"], quant="fp16", context=8192)
    assert res.fits
    assert res.headroom_gib > 100  # 8B en 192 GiB sobra muchísimo


def test_405b_no_entra_fp16_en_b200():
    spec = get_model("llama-3.1-405b")
    res = check_fit(spec, HARDWARE_PRESETS["b200"], quant="fp16", context=8192)
    assert not res.fits  # ~810 GiB de pesos no caben en 192


def test_kv_cache_crece_con_contexto():
    spec = get_model("llama-3.1-70b")
    corto = check_fit(spec, HARDWARE_PRESETS["b200"], quant="fp16", context=4096)
    largo = check_fit(spec, HARDWARE_PRESETS["b200"], quant="fp16", context=131072)
    assert largo.kv_cache_gib > corto.kv_cache_gib


def test_recommend_quant_devuelve_algo_para_70b():
    spec = get_model("llama-3.1-70b")
    rec = recommend_quant(spec, HARDWARE_PRESETS["dgx-spark"], context=8192)
    assert rec is not None
    assert rec.fits
