"""Registro de modelos con los datos necesarios para calcular memoria.

Cada `ModelSpec` lleva lo mínimo para estimar pesos + KV cache: número de
parámetros, capas, dimensiones y configuración de atención (GQA). Esto es lo que
permite responder "¿este modelo cabe en este hardware?" sin descargarlo.

Para añadir un modelo: copia los valores de su `config.json` en Hugging Face.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    params_b: float          # parámetros en miles de millones (billions)
    n_layers: int
    hidden: int
    n_heads: int
    n_kv_heads: int          # heads de KV (GQA); = n_heads si es MHA clásico
    context_max: int
    architecture: str
    notes: str = ""

    @property
    def head_dim(self) -> int:
        return self.hidden // self.n_heads


# Subconjunto representativo. El campo clave para Magnus es que cada entrada
# permita el cálculo de VRAM; ampliar es copiar valores de config.json.
MODEL_REGISTRY: dict[str, ModelSpec] = {
    "llama-3.1-8b": ModelSpec(
        id="llama-3.1-8b", params_b=8.03, n_layers=32, hidden=4096,
        n_heads=32, n_kv_heads=8, context_max=131072, architecture="llama",
    ),
    "llama-3.1-70b": ModelSpec(
        id="llama-3.1-70b", params_b=70.6, n_layers=80, hidden=8192,
        n_heads=64, n_kv_heads=8, context_max=131072, architecture="llama",
    ),
    "llama-3.1-405b": ModelSpec(
        id="llama-3.1-405b", params_b=405.0, n_layers=126, hidden=16384,
        n_heads=128, n_kv_heads=8, context_max=131072, architecture="llama",
        notes="Multi-GPU salvo cuantización agresiva. No entra fp16 en una sola tarjeta.",
    ),
    "qwen2.5-7b": ModelSpec(
        id="qwen2.5-7b", params_b=7.62, n_layers=28, hidden=3584,
        n_heads=28, n_kv_heads=4, context_max=131072, architecture="qwen2",
    ),
    "qwen2.5-32b": ModelSpec(
        id="qwen2.5-32b", params_b=32.5, n_layers=64, hidden=5120,
        n_heads=40, n_kv_heads=8, context_max=131072, architecture="qwen2",
    ),
    "qwen2.5-72b": ModelSpec(
        id="qwen2.5-72b", params_b=72.7, n_layers=80, hidden=8192,
        n_heads=64, n_kv_heads=8, context_max=131072, architecture="qwen2",
    ),
    "mistral-7b": ModelSpec(
        id="mistral-7b", params_b=7.24, n_layers=32, hidden=4096,
        n_heads=32, n_kv_heads=8, context_max=32768, architecture="mistral",
    ),
    "mixtral-8x7b": ModelSpec(
        id="mixtral-8x7b", params_b=46.7, n_layers=32, hidden=4096,
        n_heads=32, n_kv_heads=8, context_max=32768, architecture="mixtral-moe",
        notes="MoE: cargan TODOS los expertos en VRAM (~46.7B) aunque solo se activen 2 por token.",
    ),
}


def get_model(model_id: str) -> ModelSpec:
    try:
        return MODEL_REGISTRY[model_id]
    except KeyError as exc:
        known = ", ".join(sorted(MODEL_REGISTRY))
        raise KeyError(f"Modelo desconocido: {model_id!r}. Conocidos: {known}") from exc
