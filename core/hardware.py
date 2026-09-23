"""Detección de hardware NVIDIA y presets de destino.

`detect_gpus()` lee la GPU real de la máquina vía `nvidia-smi`. Cuando se quiere
saber si un modelo entraría en una máquina que NO es la actual (p. ej. validar
desde una laptop Windows si algo cabe en el B200 del server), se usa un preset
de `HARDWARE_PRESETS`.

Jetson (Orin Nano/NX/AGX) es un caso aparte: CPU y GPU comparten la RAM, y
`nvidia-smi` responde `[N/A]` en memory.total/memory.free (medido en un Orin
Nano Super con JetPack 6.2). Ahí la memoria de la GPU ES la del sistema, y se lee
de `/proc/meminfo`. Dentro de un contenedor sin `nvidia-smi` se detecta igual por
el modelo del device tree.

VRAM siempre en GiB.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_MIB_PER_GIB = 1024.0
_KIB_PER_GIB = 1024.0**2

_MEMINFO = Path("/proc/meminfo")
_DEVICE_TREE_MODEL = Path("/proc/device-tree/model")


@dataclass(frozen=True)
class GPU:
    name: str
    total_gib: float
    free_gib: float
    index: int = 0
    # True en Jetson/DGX Spark: la "VRAM" es la RAM del sistema, compartida con
    # el SO y otros procesos. `free_gib` es entonces MemAvailable, no memoria
    # reservada a la GPU.
    unified_memory: bool = False


# VRAM (GiB) por tarjeta para destinos conocidos. Sirve para validar
# compatibilidad sin tener el hardware delante.  Clave = alias en minúsculas.
HARDWARE_PRESETS: dict[str, float] = {
    # Datacenter Blackwell / Hopper / Ampere
    "b200": 192.0,
    "b100": 192.0,
    "gb200": 192.0,        # por GPU dentro del superchip
    "h200": 141.0,
    "h100": 80.0,
    "a100-80": 80.0,
    "a100-40": 40.0,
    # NVIDIA personal AI
    "dgx-spark": 128.0,    # memoria unificada LPDDR5X
    # Jetson Orin (memoria unificada, compartida con el SO: el usable real es
    # menor — el Orin Nano de 8 GB reporta 7.4 GiB de MemTotal)
    "jetson-orin-nano": 8.0,
    "jetson-orin-nx": 16.0,
    "jetson-agx-orin": 64.0,
    # Consumo RTX
    "rtx-5090": 32.0,
    "rtx-4090": 24.0,
    "rtx-4080": 16.0,
    "rtx-3090": 24.0,
}


def _parse_mib(value: str) -> float | None:
    """MiB de nvidia-smi → float, o None si viene `[N/A]` (Jetson)."""
    try:
        return float(value)
    except ValueError:
        return None


def meminfo_kib(path: Path | None = None) -> dict[str, int]:
    """Todos los campos de /proc/meminfo en KiB. Vacío si no existe (Windows)."""
    try:
        text = (path or _MEMINFO).read_text()
    except OSError:
        return {}
    fields: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            fields[key.strip()] = int(parts[0])
    return fields


def read_meminfo(path: Path = _MEMINFO) -> tuple[float, float] | None:
    """(total, disponible) en GiB desde /proc/meminfo, o None si no existe."""
    try:
        text = path.read_text()
    except OSError:
        return None
    fields: dict[str, float] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts:
            try:
                fields[key.strip()] = float(parts[0])  # kB
            except ValueError:
                continue
    if "MemTotal" not in fields:
        return None
    total = fields["MemTotal"]
    available = fields.get("MemAvailable", fields.get("MemFree", 0.0))
    return round(total / _KIB_PER_GIB, 1), round(available / _KIB_PER_GIB, 1)


def system_memory() -> tuple[float, float] | None:
    """(total, disponible) en GiB de la RAM del sistema, en Linux y Windows.

    Windows importa por las laptops con memoria unificada (N1X): ahí la GPU
    también comparte la RAM y no hay /proc/meminfo.
    """
    mem = read_meminfo()
    if mem is not None or os.name != "nt":
        return mem
    return _windows_memory()


def _windows_memory() -> tuple[float, float] | None:
    import ctypes

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    try:
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
    except (AttributeError, OSError):
        return None
    gib = 1024.0**3
    return round(status.ullTotalPhys / gib, 1), round(status.ullAvailPhys / gib, 1)


def jetson_model(path: Path | None = None) -> str | None:
    """Nombre del Jetson según el device tree, o None si no es un Jetson.

    Docker oculta /sys/firmware, así que dentro de un contenedor
    /proc/device-tree/model no existe (comprobado en el Orin Nano). El compose
    monta el archivo del host y lo indica con MAGNUS_DEVICE_TREE_MODEL.
    """
    if path is not None:
        candidates = [path]
    else:
        candidates = [_DEVICE_TREE_MODEL]
        env = os.environ.get("MAGNUS_DEVICE_TREE_MODEL")
        if env:
            candidates.insert(0, Path(env))
    for candidate in candidates:
        try:
            raw = candidate.read_bytes()
        except OSError:
            continue
        name = raw.rstrip(b"\x00").decode(errors="replace").strip()
        return name if "jetson" in name.lower() else None
    return None


def _unified_gpu(name: str, index: int = 0) -> GPU | None:
    mem = system_memory()
    if mem is None:
        return None
    total, available = mem
    return GPU(name=name, total_gib=total, free_gib=available, index=index,
               unified_memory=True)


def detect_gpus() -> list[GPU]:
    """GPUs reales de esta máquina. Lista vacía si no hay GPU NVIDIA."""
    if shutil.which("nvidia-smi") is None:
        # Contenedor en Jetson sin nvidia-smi: el device tree basta.
        model = jetson_model()
        gpu = _unified_gpu(model) if model else None
        return [gpu] if gpu else []
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    return parse_nvidia_smi(out)


def parse_nvidia_smi(out: str) -> list[GPU]:
    """Convierte la salida CSV de nvidia-smi en GPUs.

    Si la memoria viene `[N/A]` (memoria unificada), se toma la del sistema.
    """
    gpus: list[GPU] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        idx, name, total_mib, free_mib = parts[0], parts[1], parts[2], parts[3]
        try:
            index = int(idx)
        except ValueError:
            continue
        total, free = _parse_mib(total_mib), _parse_mib(free_mib)
        if total is None:
            gpu = _unified_gpu(jetson_model() or name, index=index)
            if gpu:
                gpus.append(gpu)
            continue
        gpus.append(
            GPU(
                index=index,
                name=name,
                total_gib=round(total / _MIB_PER_GIB, 1),
                free_gib=round((free or 0.0) / _MIB_PER_GIB, 1),
            )
        )
    return gpus


def resolve_target_vram_gb(target: str | None) -> float:
    """VRAM (GiB) de un destino: alias de preset, número crudo, o 'auto'.

    - `"b200"`        -> 192.0   (preset)
    - `"48"`          -> 48.0    (número explícito de GiB)
    - `None`/`"auto"` -> VRAM de la GPU 0 real, o error si no hay GPU
    """
    if target and target not in ("auto",):
        key = target.lower()
        if key in HARDWARE_PRESETS:
            return HARDWARE_PRESETS[key]
        try:
            return float(target)
        except ValueError as exc:
            raise ValueError(
                f"Destino desconocido: {target!r}. Usa un preset "
                f"({', '.join(sorted(HARDWARE_PRESETS))}), un número en GiB, o 'auto'."
            ) from exc

    gpus = detect_gpus()
    if not gpus:
        raise ValueError(
            "No se detectó GPU NVIDIA en esta máquina. Indica un destino "
            "explícito, p. ej. --target b200."
        )
    return gpus[0].total_gib
