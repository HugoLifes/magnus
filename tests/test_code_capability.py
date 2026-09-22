"""Qué puede hacer Magnus Code en cada clase de equipo."""

from __future__ import annotations

import pytest

from core.code.capability import (
    AUTO_MIN_GIB,
    CodeTier,
    capability_for,
    tier_for,
)
from core.code.permissions import Mode
from core.hardware import GPU
from core.platform import detect_platform


def equipo(total_gib: float, *, unified: bool = False) -> tuple:
    """Un equipo con una GPU de ese tamaño, con su perfil de plataforma."""
    nombre = "NVIDIA Jetson Orin Nano" if unified else "NVIDIA GeForce RTX 4080"
    gpu = GPU(index=0, name=nombre, total_gib=total_gib, free_gib=total_gib * 0.95,
              unified_memory=unified)
    return detect_platform([gpu]), gpu


@pytest.mark.parametrize("usable,esperado", [
    (3.0, CodeTier.EDGE),
    (5.9, CodeTier.EDGE),
    (8.0, CodeTier.BASIC),
    (16.0, CodeTier.CAPABLE),
    (24.0, CodeTier.PRO),
    (80.0, CodeTier.PRO),
])
def test_niveles_por_memoria(usable, esperado):
    assert tier_for(usable) is esperado


def test_equipo_chico_no_promete_lo_que_no_puede():
    """Una GTX 1650 de 4 GiB: acompaña, pero no trabaja sola."""
    profile, gpu = equipo(4.0)
    cap = capability_for(profile, gpu, sandbox_available=True)
    assert cap.tier is CodeTier.EDGE
    assert Mode.PLAN in cap.modes and Mode.ASK in cap.modes
    assert not cap.can_autonomous
    # Y dice qué hacer en su lugar, no solo que no se puede.
    assert any("red" in a or "Cloud" in a or "permiso" in a for a in cap.advice)


def test_equipo_capaz_recomienda_modelo_y_dice_cuanto_pesa():
    profile, gpu = equipo(16.0)
    cap = capability_for(profile, gpu, sandbox_available=True)
    assert cap.recommended is not None
    assert cap.recommended.params_b >= 6
    assert f"{cap.recommended.size_gib:.1f} GiB" in cap.headline
    assert any("magnus fetch" in a for a in cap.advice)


def test_si_ya_esta_descargado_no_dice_que_lo_descargues():
    profile, gpu = equipo(16.0)
    primero = capability_for(profile, gpu)
    cap = capability_for(profile, gpu, local_models=(primero.recommended.id,))
    assert cap.downloaded
    assert "descargado" in cap.headline
    assert not any("magnus fetch" in a for a in cap.advice)


def test_el_modo_autonomo_pide_sandbox():
    profile, gpu = equipo(24.0)
    sin = capability_for(profile, gpu, sandbox_available=False)
    con = capability_for(profile, gpu, sandbox_available=True)
    assert not sin.can_autonomous
    assert any("sandbox" in a for a in sin.advice)
    assert con.can_autonomous


def test_memoria_justa_explica_el_umbral():
    profile, gpu = equipo(10.0)
    cap = capability_for(profile, gpu, sandbox_available=True)
    assert not cap.can_autonomous
    assert any(f"{AUTO_MIN_GIB:.0f} GiB" in a for a in cap.advice)


def test_jetson_con_memoria_unificada():
    """El Orin Nano de 8 GiB comparte memoria con el sistema: queda poco de verdad."""
    profile, gpu = equipo(8.0, unified=True)
    cap = capability_for(profile, gpu, sandbox_available=True)
    assert cap.tier in (CodeTier.EDGE, CodeTier.BASIC)
    assert not cap.can_autonomous


def test_sin_gpu_sugiere_otro_equipo():
    profile = detect_platform([])
    cap = capability_for(profile, None)
    assert cap.recommended is None
    assert any("red" in a for a in cap.advice)
    assert Mode.EDIT not in cap.modes


def test_para_la_app_va_serializado():
    profile, gpu = equipo(16.0)
    datos = capability_for(profile, gpu, sandbox_available=True).to_dict()
    assert datos["tier"] in [t.value for t in CodeTier]
    assert datos["tier_label"]
    assert datos["recommended_model"]["download_gib"] > 0
    assert isinstance(datos["modes"], list) and datos["modes"]
