"""Liberación de caché antes de cargar en memoria unificada. SIN GPU."""

from __future__ import annotations

import pytest

from core.hardware import meminfo_kib
from core.reclaim import reclaim_for, touch_memory

GIB_KIB = 1024**2


class FakeMeminfo:
    """Simula el kernel: tocar memoria convierte caché en MemFree."""

    def __init__(self, free_gib, available_gib):
        self.free = free_gib
        self.available = available_gib
        self.touched: list[float] = []

    def read(self):
        return {"MemFree": int(self.free * GIB_KIB), "MemAvailable": int(self.available * GIB_KIB)}

    def touch(self, gib):
        self.touched.append(gib)
        self.free = min(self.available, self.free + gib)


def test_caso_medido_en_el_jetson():
    # MemFree 265 MiB, MemAvailable 2.7 GiB; el modelo necesita 1.8 GiB + 0.6 de holgura.
    kernel = FakeMeminfo(free_gib=0.26, available_gib=2.7)
    final = reclaim_for(1.8, read=kernel.read, toucher=kernel.touch)
    assert kernel.touched[0] == pytest.approx(2.4 - 0.26 + 0.25, abs=1e-3)
    assert final >= 2.4


def test_segundo_intento_desaloja_todo():
    kernel = FakeMeminfo(free_gib=0.6, available_gib=2.0)
    reclaim_for(float("inf"), read=kernel.read, toucher=kernel.touch)
    assert kernel.touched[0] == pytest.approx(2.0 - 0.25, abs=1e-3)


def test_no_toca_si_ya_hay_libre():
    kernel = FakeMeminfo(free_gib=3.0, available_gib=3.5)
    assert reclaim_for(1.8, read=kernel.read, toucher=kernel.touch) == 3.0
    assert kernel.touched == []


def test_nunca_toca_mas_de_lo_recuperable():
    kernel = FakeMeminfo(free_gib=0.2, available_gib=1.0)
    reclaim_for(6.0, read=kernel.read, toucher=kernel.touch)
    assert kernel.touched == [1.0 - 0.25]


def test_sin_meminfo_no_hace_nada():
    llamado = []
    assert reclaim_for(1.0, read=dict, toucher=llamado.append) is None
    assert llamado == []


def test_touch_memory_pequeno():
    touch_memory(0.001)  # 1 MiB: no debe fallar
    touch_memory(0)


def test_meminfo_kib(tmp_path):
    f = tmp_path / "meminfo"
    f.write_text("MemTotal:        7802680 kB\nMemFree:          259196 kB\nHugePages_Total:       0\n")
    campos = meminfo_kib(f)
    assert campos["MemFree"] == 259196
    assert campos["HugePages_Total"] == 0
    assert meminfo_kib(tmp_path / "no-existe") == {}
