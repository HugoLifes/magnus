"""Detección de Jetson (memoria unificada). Corren SIN GPU, con archivos falsos."""

from pathlib import Path

import pytest

from core import hardware
from core.hardware import (
    HARDWARE_PRESETS,
    detect_gpus,
    jetson_model,
    parse_nvidia_smi,
    read_meminfo,
)

# Valores reales de un Jetson Orin Nano Super (JetPack 6.2).
_MEMINFO_ORIN = """MemTotal:        7802680 kB
MemFree:          112640 kB
MemAvailable:    2962984 kB
Buffers:           10240 kB
"""
_MODELO_ORIN = b"NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super\x00"
_SMI_ORIN = "0, Orin (nvgpu), [N/A], [N/A]\n"


@pytest.fixture
def orin(tmp_path: Path, monkeypatch):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(_MEMINFO_ORIN)
    model = tmp_path / "model"
    model.write_bytes(_MODELO_ORIN)
    monkeypatch.setattr(hardware, "_MEMINFO", meminfo)
    monkeypatch.setattr(hardware, "_DEVICE_TREE_MODEL", model)
    # Los defaults de las funciones se evalúan al importar: se reenvuelven.
    monkeypatch.setattr(hardware, "read_meminfo", lambda path=meminfo: read_meminfo(path))
    monkeypatch.setattr(hardware, "jetson_model", lambda path=model: jetson_model(path))
    return tmp_path


def test_read_meminfo_en_gib(tmp_path):
    f = tmp_path / "meminfo"
    f.write_text(_MEMINFO_ORIN)
    assert read_meminfo(f) == (7.4, 2.8)


def test_read_meminfo_sin_archivo(tmp_path):
    assert read_meminfo(tmp_path / "no-existe") is None


def test_jetson_model_quita_nul(tmp_path):
    f = tmp_path / "model"
    f.write_bytes(_MODELO_ORIN)
    assert jetson_model(f) == "NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super"


def test_jetson_model_no_jetson(tmp_path):
    f = tmp_path / "model"
    f.write_bytes(b"Raspberry Pi 5\x00")
    assert jetson_model(f) is None


def test_jetson_model_desde_variable_de_entorno(tmp_path, monkeypatch):
    # Caso contenedor: /proc/device-tree no existe, el archivo va montado.
    montado = tmp_path / "device-tree-model"
    montado.write_bytes(_MODELO_ORIN)
    monkeypatch.setattr(hardware, "_DEVICE_TREE_MODEL", tmp_path / "no-existe")
    monkeypatch.setenv("MAGNUS_DEVICE_TREE_MODEL", str(montado))
    assert "Orin Nano" in jetson_model()


def test_nvidia_smi_na_usa_memoria_del_sistema(orin):
    gpus = parse_nvidia_smi(_SMI_ORIN)
    assert len(gpus) == 1
    g = gpus[0]
    assert g.unified_memory is True
    assert g.total_gib == 7.4
    assert g.free_gib == 2.8
    assert "Orin Nano" in g.name


def test_nvidia_smi_discreta_no_cambia():
    gpus = parse_nvidia_smi("0, NVIDIA B200, 183359, 180000\n")
    assert gpus[0].total_gib == 179.1
    assert gpus[0].unified_memory is False


def test_contenedor_sin_nvidia_smi_detecta_jetson(orin, monkeypatch):
    monkeypatch.setattr(hardware.shutil, "which", lambda _: None)
    gpus = detect_gpus()
    assert len(gpus) == 1 and gpus[0].unified_memory


def test_sin_nvidia_smi_ni_jetson(monkeypatch, tmp_path):
    monkeypatch.setattr(hardware.shutil, "which", lambda _: None)
    monkeypatch.setattr(hardware, "jetson_model", lambda: None)
    assert detect_gpus() == []


def test_presets_jetson():
    assert HARDWARE_PRESETS["jetson-orin-nano"] == 8.0
    assert HARDWARE_PRESETS["jetson-agx-orin"] == 64.0


def test_aviso_memoria_unificada_cuando_no_cabe_en_lo_libre():
    from core import check_fit, get_model, unified_memory_note

    # Caso medido: 7.4 GiB totales, 2.8 libres con el aforo corriendo.
    res = check_fit(get_model("llama-3.1-8b"), 7.4, quant="q4", context=4096)
    assert res.fits  # sobre el total "entra"...
    assert "Memoria unificada" in unified_memory_note(res, free_gib=2.8)  # ...pero no cabe


def test_sin_aviso_si_cabe_en_lo_libre():
    from core import check_fit, get_model, unified_memory_note

    res = check_fit(get_model("qwen2.5-1.5b"), 7.4, quant="q4", context=4096)
    assert unified_memory_note(res, free_gib=2.8) is None
