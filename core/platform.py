"""Familia de plataforma NVIDIA y el perfil de servicio que le corresponde.

Magnus tiene que sentirse en casa en toda la familia NVIDIA, desde un Jetson de
8 GB hasta un B200. Lo que cambia entre ellos no es la API — es qué runtime
conviene, cuántos modelos caben a la vez y qué tamaño de modelo es razonable.
Este módulo traduce "qué hardware hay" en "cómo servir aquí", para que ni la
CLI ni el cliente Flutter tengan que saber de hardware.

`profile_for` no hace E/S: se testea sin GPU.
"""

from __future__ import annotations

import enum
import re
from dataclasses import asdict, dataclass, field, replace

from core.hardware import GPU, detect_gpus
from core.runtimes import Runtime


class PlatformFamily(str, enum.Enum):
    JETSON = "jetson"            # Orin Nano/NX/AGX: memoria unificada, arm64, edge
    DGX_SPARK = "dgx-spark"      # GB10: memoria unificada 128 GB, arm64, escritorio
    GEFORCE_RTX = "geforce-rtx"  # consumo y laptops: 4–32 GB dedicados
    WORKSTATION = "workstation"  # RTX PRO / Ada / serie A: 8–96 GB dedicados
    DATACENTER = "datacenter"    # A100/H100/H200/B200: 40–192 GB, multiusuario
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PlatformProfile:
    family: PlatformFamily
    display_name: str
    unified_memory: bool
    # Orden de preferencia de runtimes para esta familia.
    runtimes: list[Runtime]
    # Modelos que conviene tener cargados a la vez.
    max_loaded_models: int
    # Peticiones concurrentes razonables por modelo.
    parallel_requests: int
    # Tamaño orientativo (B de parámetros, q4, ctx 4096) que sirve con holgura.
    suggested_max_params_b: float
    # Memoria a reservar para el SO y otros procesos (solo unificada).
    reserve_gib: float = 0.0
    gpu_count: int = 0
    total_memory_gib: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self) | {
            "family": self.family.value,
            "runtimes": [rt.value for rt in self.runtimes],
        }


# Con palabras completas: "RTX A4000" contiene "a40" y "RTX A1000" contiene
# "a100", y ninguna es de datacenter.
_WORKSTATION = re.compile(r"rtx\s*(pro\b|a\d{3,4}\b|\d{4}\s*ada)|quadro")
_DATACENTER = re.compile(r"\b(gb200|b200|b100|h200|h100|h800|h20|a100|a800|a40|a30|a10|l40s?|l4)\b")
_SPARK = re.compile(r"\bgb10\b|spark")


def classify(gpu: GPU | None) -> PlatformFamily:
    """Familia de plataforma a partir de la GPU detectada."""
    if gpu is None:
        return PlatformFamily.UNKNOWN
    name = gpu.name.lower()
    if "jetson" in name or "orin" in name:
        return PlatformFamily.JETSON
    if _SPARK.search(name):
        return PlatformFamily.DGX_SPARK
    if _WORKSTATION.search(name):
        return PlatformFamily.WORKSTATION
    if _DATACENTER.search(name):
        return PlatformFamily.DATACENTER
    if "geforce" in name or "rtx" in name or "gtx" in name:
        return PlatformFamily.GEFORCE_RTX
    if gpu.unified_memory:
        return PlatformFamily.JETSON
    return PlatformFamily.UNKNOWN


def profile_for(gpu: GPU | None) -> PlatformProfile:
    """Perfil de servicio recomendado para una GPU (o varias sumadas)."""
    profile = _base_profile(gpu)
    if gpu is None:
        return profile
    return replace(profile, gpu_count=1, total_memory_gib=gpu.total_gib)


def detect_platform(gpus: list[GPU] | None = None) -> PlatformProfile:
    """Perfil de esta máquina. Con varias GPUs cuenta la memoria conjunta."""
    gpus = detect_gpus() if gpus is None else gpus
    if not gpus:
        return profile_for(None)
    primary = gpus[0]
    if len(gpus) > 1:
        # Ollama reparte las capas de un modelo entre GPUs, y cada GPU de más
        # permite tener otro modelo cargado.
        primary = GPU(
            name=primary.name,
            total_gib=round(sum(g.total_gib for g in gpus), 1),
            free_gib=round(sum(g.free_gib for g in gpus), 1),
            unified_memory=primary.unified_memory,
        )
    profile = profile_for(primary)
    return replace(
        profile,
        gpu_count=len(gpus),
        max_loaded_models=max(profile.max_loaded_models, len(gpus)),
    )


def _base_profile(gpu: GPU | None) -> PlatformProfile:
    family = classify(gpu)
    total = gpu.total_gib if gpu else 0.0
    name = gpu.name if gpu else "Sin GPU NVIDIA"

    if family is PlatformFamily.JETSON:
        # Medido en Orin Nano Super 8 GB: el SO y el escritorio ocupan ~1.5 GiB
        # sin carga. En 8 GB solo cabe un modelo pequeño a la vez.
        reserve = 1.5 if total <= 8.5 else 3.0
        return PlatformProfile(
            family=family, display_name=name, unified_memory=True,
            runtimes=[Runtime.OLLAMA, Runtime.LLAMACPP, Runtime.TRTLLM],
            max_loaded_models=1, parallel_requests=1,
            suggested_max_params_b=_params_for(total - reserve),
            reserve_gib=reserve,
            notes=[
                "Memoria compartida con el SO: si se agota, se cuelga el equipo entero.",
                "Ollama en Docker: la imagen oficial ollama/ollama trae soporte JetPack 6.",
                "Modo de energía máximo: sudo nvpmodel -m 0 (MAXN).",
            ],
        )
    if family is PlatformFamily.DGX_SPARK:
        return PlatformProfile(
            family=family, display_name=name, unified_memory=True,
            runtimes=[Runtime.VLLM, Runtime.OLLAMA, Runtime.TRTLLM],
            max_loaded_models=3, parallel_requests=4,
            suggested_max_params_b=_params_for(total - 8.0),
            reserve_gib=8.0,
        )
    if family is PlatformFamily.DATACENTER:
        return PlatformProfile(
            family=family, display_name=name, unified_memory=False,
            runtimes=[Runtime.VLLM, Runtime.TRTLLM, Runtime.OLLAMA],
            max_loaded_models=4, parallel_requests=32,
            suggested_max_params_b=_params_for(total),
            notes=["Multiusuario: vLLM con batching continuo rinde mucho más que Ollama."],
        )
    if family is PlatformFamily.WORKSTATION:
        return PlatformProfile(
            family=family, display_name=name, unified_memory=False,
            runtimes=[Runtime.VLLM, Runtime.OLLAMA, Runtime.LLAMACPP],
            max_loaded_models=2, parallel_requests=8,
            suggested_max_params_b=_params_for(total),
        )
    if family is PlatformFamily.GEFORCE_RTX:
        return PlatformProfile(
            family=family, display_name=name, unified_memory=False,
            runtimes=[Runtime.OLLAMA, Runtime.LLAMACPP, Runtime.VLLM],
            max_loaded_models=1 if total < 16 else 2,
            parallel_requests=2,
            suggested_max_params_b=_params_for(total),
            notes=["El escritorio usa parte de la VRAM: deja ~1 GiB de margen."],
        )
    return PlatformProfile(
        family=PlatformFamily.UNKNOWN, display_name=name, unified_memory=False,
        runtimes=[Runtime.OLLAMA], max_loaded_models=1, parallel_requests=1,
        suggested_max_params_b=0.0,
        notes=["No se reconoció una GPU NVIDIA. Indica un destino con --target."],
    )


def _params_for(usable_gib: float) -> float:
    """Parámetros (B) que caben en q4 con ctx 4096, con el overhead de Magnus.

    q4 = 0.5 bytes/param → 1 GiB de pesos ≈ 2.147 B. Se descuenta 1 GiB de
    contexto CUDA, ~0.5 GiB de KV cache y un 20 % de overhead, igual que
    `compatibility.check_fit`. Redondeo hacia abajo al medio B.
    """
    weights_gib = (usable_gib - 1.5) / 1.2
    if weights_gib <= 0:
        return 0.0
    params = weights_gib * 1024**3 / 0.5 / 1e9
    return int(params * 2) / 2
