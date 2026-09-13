"""Endpoints /platform y /system. Corren SIN GPU (se inyecta el hardware)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import daemon.app as app_module
from core.hardware import GPU
from core.platform import detect_platform
from core.telemetry import GpuSample, SystemSample

client = TestClient(app_module.api)


def test_platform_jetson(monkeypatch):
    orin = GPU(name="NVIDIA Jetson Orin Nano", total_gib=7.4, free_gib=2.8, unified_memory=True)
    monkeypatch.setattr(app_module, "detect_platform", lambda: detect_platform([orin]))
    body = client.get("/platform").json()
    assert body["family"] == "jetson"
    assert body["runtimes"][0] == "ollama"
    assert body["unified_memory"] is True
    assert body["max_loaded_models"] == 1


def test_platform_dos_gpus_suman_memoria(monkeypatch):
    gpus = [GPU(name="NVIDIA GeForce RTX 4090", total_gib=24.0, free_gib=23.0, index=i)
            for i in range(2)]
    monkeypatch.setattr(app_module, "detect_platform", lambda: detect_platform(gpus))
    body = client.get("/platform").json()
    assert body["gpu_count"] == 2
    assert body["total_memory_gib"] == 48.0
    assert body["max_loaded_models"] == 2


def test_system(monkeypatch):
    muestra = SystemSample(
        timestamp=1.0,
        gpus=[GpuSample(0, "NVIDIA GeForce GTX 1650", 3.0, 17.32, 50.0, 4.0, 0.16)],
        ram_total_gib=15.7, ram_available_gib=8.0,
    )
    monkeypatch.setattr(app_module, "sample_system", lambda: muestra)
    body = client.get("/system").json()
    assert body["power_w"] == 17.32
    assert body["gpus"][0]["temperature_c"] == 50.0
