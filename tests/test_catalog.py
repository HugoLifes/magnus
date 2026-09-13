"""Catálogo, recomendación por hardware y guarda de memoria. Corren SIN GPU."""

from __future__ import annotations

import pytest

from core.catalog import (
    CATALOG,
    CODE,
    EMBEDDING,
    best_fit,
    get_catalog_model,
    recommend,
    usable_gib,
)
from core.compatibility import load_memory_verdict, ollama_required_gib
from core.hardware import GPU
from core.platform import detect_platform

# Casos medidos o reales.
ORIN = GPU("NVIDIA Jetson Orin Nano", total_gib=7.4, free_gib=2.7, unified_memory=True)
GTX1650 = GPU("NVIDIA GeForce GTX 1650", total_gib=4.0, free_gib=3.9)
RTX4090 = GPU("NVIDIA GeForce RTX 4090", total_gib=24.0, free_gib=23.0)


def test_catalogo_sin_ids_repetidos_y_con_datos():
    ids = [m.id for m in CATALOG]
    assert len(ids) == len(set(ids))
    for m in CATALOG:
        assert m.size_gib > 0 and m.params_b > 0 and m.capabilities


def test_memoria_requerida():
    # Caso medido: 0.92 GiB de descarga → Ollama reservó 1.74 GiB.
    assert ollama_required_gib(0.92) == 1.8
    assert ollama_required_gib(4.8) == 6.5


def test_memoria_util_por_familia():
    assert usable_gib(detect_platform([ORIN]), ORIN) == 2.1        # libre − holgura CUDA
    assert usable_gib(detect_platform([GTX1650]), GTX1650) == 3.0  # total − escritorio
    dos = [RTX4090, RTX4090]
    assert usable_gib(detect_platform(dos), RTX4090) == 47.0       # GPUs sumadas
    assert usable_gib(detect_platform([]), None) == 0.0


def test_jetson_con_el_aforo_corriendo():
    elegido = best_fit(detect_platform([ORIN]), ORIN)
    assert elegido is not None
    assert ollama_required_gib(elegido.size_gib) <= 2.1
    recs = {r.model.id: r for r in recommend(detect_platform([ORIN]), ORIN)}
    assert recs["deepseek-r1:1.5b"].fits
    assert not recs["qwen3:1.7b"].fits  # 2.3 + 0.6 de CUDA no entra en 2.7 libres
    assert recs["qwen3:4b"].note is None  # en unificada no se ofrece "repartir con CPU"


def test_laptop_4gb():
    p = detect_platform([GTX1650])
    assert best_fit(p, GTX1650).id == "llama3.2:3b" or best_fit(p, GTX1650).params_b <= 3.2
    recs = {r.model.id: r for r in recommend(p, GTX1650)}
    assert recs["qwen3:4b"].note  # dedicada: cabría repartido


def test_rtx_4090_y_capacidades():
    p = detect_platform([RTX4090])
    assert best_fit(p, RTX4090).params_b >= 30
    assert best_fit(p, RTX4090, CODE).id == "qwen2.5-coder:32b"
    assert all(EMBEDDING in r.model.capabilities for r in recommend(p, RTX4090, EMBEDDING))


def test_orden_primero_lo_que_cabe():
    recs = recommend(detect_platform([ORIN]), ORIN)
    fits = [r.fits for r in recs]
    assert fits == sorted(fits, reverse=True)


def test_get_catalog_model():
    assert get_catalog_model("nomic-embed-text").capabilities == (EMBEDDING,)
    assert get_catalog_model("no-existe") is None


@pytest.mark.parametrize(
    ("size", "gpu", "permitido", "aviso"),
    [
        (1.0, ORIN, True, False),     # 1.9 + 0.6 GiB en 2.7 libres
        (1.3, ORIN, False, True),     # 2.3 + 0.6 GiB no entra en 2.7 libres
        (4.8, ORIN, False, True),     # 6.0 GiB en 2.7 libres: se niega
        (4.8, RTX4090, True, False),
        (18.6, GTX1650, True, True),  # dedicada: se permite con aviso de CPU
        (None, ORIN, True, False),    # tamaño desconocido: no se bloquea
        (4.8, None, True, False),
    ],
)
def test_guarda_de_memoria(size, gpu, permitido, aviso):
    ok, note = load_memory_verdict(size, gpu)
    assert ok is permitido
    assert (note is not None) is aviso
