"""Magnus core — lógica pura, sin dependencias de framework.

Todo lo que vive aquí debe ser testeable sin GPU y sin servidor: detección de
hardware, registro de modelos, cálculo de compatibilidad y abstracción de
runtimes. El daemon (FastAPI) y la CLI (Typer) son envoltorios delgados sobre
estas funciones.
"""

from core.compatibility import CompatibilityResult, check_fit, recommend_quant
from core.hardware import GPU, HARDWARE_PRESETS, detect_gpus, resolve_target_vram_gb
from core.model_registry import MODEL_REGISTRY, ModelSpec, get_model
from core.runtimes import Runtime, runtimes_for_quant

__all__ = [
    "CompatibilityResult",
    "check_fit",
    "recommend_quant",
    "GPU",
    "HARDWARE_PRESETS",
    "detect_gpus",
    "resolve_target_vram_gb",
    "MODEL_REGISTRY",
    "ModelSpec",
    "get_model",
    "Runtime",
    "runtimes_for_quant",
]
