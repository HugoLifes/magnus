"""Tests de detección de hardware y presets. Corren SIN GPU."""

import pytest

from core.hardware import HARDWARE_PRESETS, resolve_target_vram_gb


def test_presets_tienen_valores_positivos():
    for name, vram in HARDWARE_PRESETS.items():
        assert vram > 0, f"Preset {name!r} con VRAM <= 0"


def test_b200_es_192():
    assert HARDWARE_PRESETS["b200"] == 192.0


def test_resolve_preset_conocido():
    assert resolve_target_vram_gb("b200") == 192.0
    assert resolve_target_vram_gb("h100") == 80.0
    assert resolve_target_vram_gb("dgx-spark") == 128.0


def test_resolve_preset_case_insensitive():
    assert resolve_target_vram_gb("B200") == 192.0
    assert resolve_target_vram_gb("RTX-4090") == 24.0


def test_resolve_numero_crudo():
    assert resolve_target_vram_gb("48") == 48.0
    assert resolve_target_vram_gb("16.5") == 16.5


def test_resolve_destino_desconocido_lanza_error():
    with pytest.raises(ValueError, match="Destino desconocido"):
        resolve_target_vram_gb("tarjeta-magica")


def test_resolve_auto_sin_gpu_lanza_error(monkeypatch):
    monkeypatch.setattr("core.hardware.detect_gpus", lambda: [])
    with pytest.raises(ValueError, match="No se detectó GPU"):
        resolve_target_vram_gb("auto")


def test_resolve_none_sin_gpu_lanza_error(monkeypatch):
    monkeypatch.setattr("core.hardware.detect_gpus", lambda: [])
    with pytest.raises(ValueError, match="No se detectó GPU"):
        resolve_target_vram_gb(None)
