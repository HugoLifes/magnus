"""Liberar la caché de páginas antes de cargar un modelo en memoria unificada.

Medido en un Jetson Orin Nano Super con otro contenedor corriendo: MemAvailable
2.7 GiB pero MemFree 253 MiB — 2.3 GiB eran caché de archivos. Ollama mira lo
disponible, decide que un modelo de 1.7 GiB cabe, y CUDA falla:
`NvMapMemAllocInternalTagged ... error 12` / `cudaMalloc failed: out of memory`.
En Tegra las reservas de la GPU salen de NvMap, que no espera a que el kernel
desaloje la caché.

La receta habitual es `echo 3 > /proc/sys/vm/drop_caches`, que exige root. Sin
root funciona igual escribir en memoria anónima el hueco que falta: el kernel
desaloja caché para dárnosla y, al soltarla, queda libre de verdad. Medido:
tocar 1.5 GiB subió MemFree de 265 MiB a 1.68 GiB, y la misma carga que fallaba
entró en 2.5 s.
"""

from __future__ import annotations

from collections.abc import Callable

from core.compatibility import UNIFIED_CUDA_HEADROOM_GIB
from core.hardware import meminfo_kib

_KIB_PER_GIB = 1024**2
_PAGE_BYTES = 4096
# Margen para no empujar al sistema a swap: nunca se toca todo lo recuperable.
_MARGIN_GIB = 0.25


def touch_memory(gib: float) -> None:
    """Escribe una página de cada 4 KiB en `gib` de memoria anónima y la suelta."""
    size = int(gib * 1024**3)
    if size <= 0:
        return
    block = bytearray(size)
    block[::_PAGE_BYTES] = b"\x01" * len(range(0, size, _PAGE_BYTES))
    del block


def reclaim_for(
    needed_gib: float,
    *,
    read: Callable[[], dict[str, int]] = meminfo_kib,
    toucher: Callable[[float], None] = touch_memory,
) -> float | None:
    """Intenta dejar `needed_gib` (más holgura de CUDA) en MemFree desalojando caché.

    Con `needed_gib=float("inf")` desaloja todo lo que se puede sin swap: es el
    segundo intento cuando una carga ya falló por memoria.
    Devuelve MemFree final en GiB, o None si no hay /proc/meminfo (Windows).
    """
    info = read()
    if "MemFree" not in info:
        return None
    free = info["MemFree"] / _KIB_PER_GIB
    target = needed_gib + UNIFIED_CUDA_HEADROOM_GIB
    if free >= target:
        return round(free, 2)
    available = info.get("MemAvailable", info["MemFree"]) / _KIB_PER_GIB
    amount = min(target - free + _MARGIN_GIB, available - _MARGIN_GIB)
    if amount <= 0:
        return round(free, 2)
    toucher(amount)
    after = read()
    return round(after["MemFree"] / _KIB_PER_GIB, 2) if "MemFree" in after else None
