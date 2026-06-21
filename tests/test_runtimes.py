"""Tests de la abstracción de runtimes. Corren SIN GPU."""

from core.runtimes import Runtime, runtimes_for_quant


def test_fp16_solo_vllm_y_trtllm():
    rts = runtimes_for_quant("fp16")
    assert Runtime.VLLM in rts
    assert Runtime.TRTLLM in rts
    assert Runtime.OLLAMA not in rts


def test_q4_en_todos_los_runtimes():
    rts = runtimes_for_quant("q4")
    assert Runtime.OLLAMA in rts
    assert Runtime.VLLM in rts
    assert Runtime.TRTLLM in rts


def test_q6_solo_ollama():
    rts = runtimes_for_quant("q6")
    assert Runtime.OLLAMA in rts
    assert Runtime.VLLM not in rts
    assert Runtime.TRTLLM not in rts


def test_cuant_desconocida_devuelve_lista_vacia():
    assert runtimes_for_quant("q2") == []
    assert runtimes_for_quant("bf16") == []


def test_runtime_enum_valores():
    assert Runtime.OLLAMA.value == "ollama"
    assert Runtime.VLLM.value == "vllm"
    assert Runtime.TRTLLM.value == "trtllm"
