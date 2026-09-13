"""Clasificación por familia NVIDIA y perfil de servicio. Corren SIN GPU."""

from __future__ import annotations

import pytest

from core.hardware import GPU
from core.platform import PlatformFamily, _params_for, classify, profile_for
from core.runtimes import Runtime


@pytest.mark.parametrize(
    ("nombre", "familia"),
    [
        ("NVIDIA GeForce RTX 4060 Laptop GPU", PlatformFamily.GEFORCE_RTX),
        ("NVIDIA GeForce GTX 1650", PlatformFamily.GEFORCE_RTX),
        ("NVIDIA GeForce RTX 5090", PlatformFamily.GEFORCE_RTX),
        ("NVIDIA RTX PRO 6000 Blackwell Workstation Edition", PlatformFamily.WORKSTATION),
        ("NVIDIA RTX 6000 Ada Generation", PlatformFamily.WORKSTATION),
        # "a4000" contiene "a40" y "a1000" contiene "a100": no son datacenter.
        ("NVIDIA RTX A4000", PlatformFamily.WORKSTATION),
        ("NVIDIA RTX A1000 Laptop GPU", PlatformFamily.WORKSTATION),
        ("NVIDIA B200", PlatformFamily.DATACENTER),
        ("NVIDIA A100-SXM4-80GB", PlatformFamily.DATACENTER),
        ("NVIDIA H100 80GB HBM3", PlatformFamily.DATACENTER),
        ("NVIDIA L40S", PlatformFamily.DATACENTER),
        ("NVIDIA GB10", PlatformFamily.DGX_SPARK),
        ("NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super",
         PlatformFamily.JETSON),
    ],
)
def test_clasifica_familias(nombre, familia):
    assert classify(GPU(name=nombre, total_gib=8.0, free_gib=8.0)) is familia


def test_sin_gpu_es_desconocida():
    assert classify(None) is PlatformFamily.UNKNOWN
    assert profile_for(None).suggested_max_params_b == 0.0


def test_perfil_jetson_orin_nano():
    gpu = GPU(name="NVIDIA Jetson Orin Nano", total_gib=7.4, free_gib=2.8, unified_memory=True)
    p = profile_for(gpu)
    assert p.family is PlatformFamily.JETSON
    assert p.unified_memory
    assert p.max_loaded_models == 1
    assert p.runtimes[0] is Runtime.OLLAMA
    assert p.suggested_max_params_b == 7.5


def test_perfil_datacenter_prefiere_vllm():
    p = profile_for(GPU(name="NVIDIA B200", total_gib=179.1, free_gib=179.0))
    assert p.runtimes[0] is Runtime.VLLM
    assert p.max_loaded_models > 1


def test_perfil_laptop_4gb():
    p = profile_for(GPU(name="NVIDIA GeForce GTX 1650", total_gib=4.0, free_gib=3.8))
    assert p.family is PlatformFamily.GEFORCE_RTX
    assert p.suggested_max_params_b == 4.0


def test_params_sin_memoria():
    assert _params_for(1.0) == 0.0
    assert _params_for(0.0) == 0.0
