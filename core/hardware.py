"""Detección de hardware NVIDIA y presets de destino.

`detect_gpus()` lee la GPU real de la máquina vía `nvidia-smi`. Cuando se quiere
saber si un modelo entraría en una máquina que NO es la actual (p. ej. validar
desde una laptop Windows si algo cabe en el B200 del server), se usa un preset
de `HARDWARE_PRESETS`.

VRAM siempre en GiB.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

_MIB_PER_GIB = 1024.0


@dataclass(frozen=True)
class GPU:
    name: str
    total_gib: float
    free_gib: float
    index: int = 0


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
    # Consumo RTX
    "rtx-5090": 32.0,
    "rtx-4090": 24.0,
    "rtx-4080": 16.0,
    "rtx-3090": 24.0,
}


def detect_gpus() -> list[GPU]:
    """GPUs reales de esta máquina. Lista vacía si no hay `nvidia-smi`/GPU."""
    if shutil.which("nvidia-smi") is None:
        return []
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

    gpus: list[GPU] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        idx, name, total_mib, free_mib = parts[0], parts[1], parts[2], parts[3]
        try:
            gpus.append(
                GPU(
                    index=int(idx),
                    name=name,
                    total_gib=round(float(total_mib) / _MIB_PER_GIB, 1),
                    free_gib=round(float(free_mib) / _MIB_PER_GIB, 1),
                )
            )
        except ValueError:
            continue
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
