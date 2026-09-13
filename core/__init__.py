"""Magnus core — lógica pura, sin dependencias de framework.

Todo lo que vive aquí debe ser testeable sin GPU y sin servidor: detección de
hardware, registro de modelos, cálculo de compatibilidad y abstracción de
runtimes. El daemon (FastAPI) y la CLI (Typer) son envoltorios delgados sobre
estas funciones.
"""

from core.compatibility import (
    CompatibilityResult,
    check_fit,
    quant_matrix,
    recommend_quant,
    unified_memory_note,
)
from core.downloader import HFDownloadResult, download_model, hf_cli_available
from core.hardware import (
    GPU,
    HARDWARE_PRESETS,
    detect_gpus,
    jetson_model,
    read_meminfo,
    resolve_target_vram_gb,
    system_memory,
)
from core.model_registry import MODEL_REGISTRY, ModelSpec, get_model
from core.platform import PlatformFamily, PlatformProfile, detect_platform, profile_for
from core.runtime_manager import LoadedModel, RuntimeBackend, RuntimeManager, RuntimeManagerError
from core.runtimes import Runtime, runtimes_for_quant
from core.telemetry import GpuSample, SystemSample, sample_system

__all__ = [
    "GPU",
    "HARDWARE_PRESETS",
    "MODEL_REGISTRY",
    "CompatibilityResult",
    "GpuSample",
    "HFDownloadResult",
    "LoadedModel",
    "ModelSpec",
    "PlatformFamily",
    "PlatformProfile",
    "Runtime",
    "RuntimeBackend",
    "RuntimeManager",
    "RuntimeManagerError",
    "SystemSample",
    "check_fit",
    "detect_gpus",
    "detect_platform",
    "download_model",
    "get_model",
    "hf_cli_available",
    "jetson_model",
    "profile_for",
    "quant_matrix",
    "read_meminfo",
    "recommend_quant",
    "resolve_target_vram_gb",
    "runtimes_for_quant",
    "sample_system",
    "system_memory",
    "unified_memory_note",
]
