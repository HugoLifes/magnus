"""Telemetría: nvidia-smi y sysfs del Jetson. Corren SIN GPU, con archivos falsos."""

from __future__ import annotations

from pathlib import Path

from core import telemetry
from core.telemetry import (
    GpuSample,
    parse_nvidia_smi_telemetry,
    read_jetson_gpu_load,
    read_power_rails,
    read_thermal,
    sample_system,
)


def _escribir(path: Path, texto: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto)


def test_nvidia_smi_gpu_dedicada():
    # Salida real de una GTX 1650 de laptop.
    gpus = parse_nvidia_smi_telemetry("0, NVIDIA GeForce GTX 1650, 0, 17.32, 50, 4096, 161\n")
    g = gpus[0]
    assert g.name == "NVIDIA GeForce GTX 1650"
    assert g.power_w == 17.32
    assert g.temperature_c == 50.0
    assert g.memory_total_gib == 4.0
    assert g.unified_memory is False


def test_nvidia_smi_na_marca_memoria_unificada():
    gpus = parse_nvidia_smi_telemetry("0, Orin (nvgpu), [N/A], [N/A], [N/A], [N/A], [N/A]\n")
    assert gpus[0].unified_memory is True
    assert gpus[0].power_w is None


def test_rails_ina3221(tmp_path):
    # Valores reales del Orin Nano en reposo.
    hw = tmp_path / "1-0040" / "hwmon" / "hwmon1"
    _escribir(hw / "in1_label", "VDD_IN\n")
    _escribir(hw / "in1_input", "4992\n")
    _escribir(hw / "curr1_input", "1472\n")
    _escribir(hw / "in2_label", "VDD_CPU_GPU_CV\n")
    _escribir(hw / "in2_input", "4984\n")
    _escribir(hw / "curr2_input", "328\n")
    _escribir(hw / "in7_label", "sum of shunt voltages\n")
    _escribir(hw / "in7_input", "12560\n")  # sin corriente: se descarta
    rails = read_power_rails(tmp_path)
    assert rails == {"VDD_IN": 7.35, "VDD_CPU_GPU_CV": 1.63}


def test_carga_gpu_jetson_en_tanto_por_mil(tmp_path):
    load = tmp_path / "load"
    load.write_text("250\n")
    assert read_jetson_gpu_load((tmp_path / "no-existe", load)) == 25.0


def test_carga_gpu_sin_archivo(tmp_path):
    assert read_jetson_gpu_load((tmp_path / "no-existe",)) is None


def test_thermal_por_tipo_y_zona_ilegible(tmp_path):
    _escribir(tmp_path / "thermal_zone0" / "type", "cpu-thermal\n")
    _escribir(tmp_path / "thermal_zone0" / "temp", "60312\n")
    _escribir(tmp_path / "thermal_zone1" / "type", "cv0-thermal\n")  # sin temp
    _escribir(tmp_path / "thermal_zone2" / "type", "gpu-thermal\n")
    _escribir(tmp_path / "thermal_zone2" / "temp", "61062\n")
    assert read_thermal("gpu-thermal", tmp_path) == 61.1
    assert read_thermal("no-existe", tmp_path) is None


def test_muestra_jetson(monkeypatch):
    monkeypatch.setattr(telemetry, "jetson_model", lambda: "NVIDIA Jetson Orin Nano")
    monkeypatch.setattr(telemetry, "system_memory", lambda: (7.4, 2.8))
    monkeypatch.setattr(telemetry, "read_power_rails",
                        lambda: {"VDD_IN": 7.35, "VDD_CPU_GPU_CV": 1.63})
    monkeypatch.setattr(telemetry, "read_jetson_gpu_load", lambda: 12.5)
    monkeypatch.setattr(telemetry, "read_thermal", lambda zone: 61.0)

    s = sample_system()
    assert s.power_w == 7.35  # la placa entera, no solo el rail de GPU
    g = s.gpus[0]
    assert g.unified_memory and g.memory_used_gib == 4.6
    assert g.utilization_pct == 12.5


def test_muestra_gpu_dedicada(monkeypatch):
    monkeypatch.setattr(telemetry, "jetson_model", lambda: None)
    monkeypatch.setattr(telemetry, "system_memory", lambda: (15.7, 8.0))
    monkeypatch.setattr(telemetry.shutil, "which", lambda _: "nvidia-smi")
    monkeypatch.setattr(telemetry, "_query_nvidia_smi", lambda: [
        GpuSample(0, "RTX 4090", 90.0, 300.0, 70.0, 24.0, 20.0),
        GpuSample(1, "RTX 4090", 80.0, 250.5, 68.0, 24.0, 18.0),
    ])
    s = sample_system()
    assert s.board_power_w is None
    assert s.power_w == 550.5  # suma de las GPUs


def test_muestra_sin_gpu(monkeypatch):
    monkeypatch.setattr(telemetry, "jetson_model", lambda: None)
    monkeypatch.setattr(telemetry, "system_memory", lambda: None)
    monkeypatch.setattr(telemetry.shutil, "which", lambda _: None)
    s = sample_system()
    assert s.gpus == [] and s.power_w is None and s.ram_total_gib is None
