"""¿Cabe este modelo en este hardware? — el cálculo central de Magnus.

Estima la VRAM necesaria para servir un modelo y la compara con la disponible
en el destino. Devuelve un veredicto accionable: si entra, cuánto margen queda,
y si no, qué cuantización sí entraría.

Modelo de memoria (aproximado pero realista):

    total = (pesos + kv_cache) * OVERHEAD + CUDA_CONTEXT

  - pesos     = params * bytes_por_parámetro(cuant)
  - kv_cache  = 2(K,V) * n_layers * n_kv_heads * head_dim * context * batch * bytes_kv
  - OVERHEAD  ~ activaciones, fragmentación, buffers del runtime
  - CUDA_CTX  ~ contexto de CUDA + workspace fijo

Es una ESTIMACIÓN de planificación, no una garantía. Para servir en producción,
medir con el runtime real. Pero distingue bien "ni de broma" de "entra sobrado".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.model_registry import ModelSpec
from core.runtimes import Runtime, runtimes_for_quant

_BYTES_PER_GIB = 1024**3

# Bytes por parámetro según cuantización (de mayor a menor calidad).
_BYTES_PER_PARAM: dict[str, float] = {
    "fp16": 2.0,
    "fp8": 1.0,
    "q8": 1.0,
    "q6": 0.75,
    "q5": 0.65,
    "q4": 0.5,
}

# Orden de preferencia: primero la mejor calidad que entre.
QUANT_PREFERENCE: list[str] = ["fp16", "fp8", "q8", "q6", "q5", "q4"]

_OVERHEAD = 1.20          # +20% activaciones/fragmentación
_CUDA_CONTEXT_GIB = 1.0   # contexto CUDA + workspace fijo


def bytes_per_param(quant: str) -> float:
    try:
        return _BYTES_PER_PARAM[quant]
    except KeyError as exc:
        raise ValueError(
            f"Cuantización desconocida: {quant!r}. Opciones: {', '.join(_BYTES_PER_PARAM)}"
        ) from exc


def estimate_weights_gib(params_b: float, quant: str) -> float:
    params = params_b * 1e9
    return params * bytes_per_param(quant) / _BYTES_PER_GIB


def estimate_kv_cache_gib(
    spec: ModelSpec, context: int, batch: int = 1, kv_bytes: float = 2.0
) -> float:
    elems = 2 * spec.n_layers * spec.n_kv_heads * spec.head_dim * context * batch
    return elems * kv_bytes / _BYTES_PER_GIB


def estimate_total_gib(
    spec: ModelSpec, quant: str, context: int, batch: int = 1
) -> float:
    weights = estimate_weights_gib(spec.params_b, quant)
    kv = estimate_kv_cache_gib(spec, context, batch)
    return (weights + kv) * _OVERHEAD + _CUDA_CONTEXT_GIB


@dataclass
class CompatibilityResult:
    model_id: str
    quant: str
    context: int
    batch: int
    required_gib: float
    available_gib: float
    weights_gib: float
    kv_cache_gib: float
    fits: bool
    headroom_gib: float
    runtimes: list[Runtime] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def utilization_pct(self) -> float:
        if self.available_gib <= 0:
            return 0.0
        return round(self.required_gib / self.available_gib * 100, 1)


def check_fit(
    spec: ModelSpec,
    available_gib: float,
    quant: str = "fp16",
    context: int | None = None,
    batch: int = 1,
) -> CompatibilityResult:
    """Veredicto de si `spec` entra en `available_gib` con la cuant/contexto dados."""
    context = context or spec.context_max
    weights = estimate_weights_gib(spec.params_b, quant)
    kv = estimate_kv_cache_gib(spec, context, batch)
    required = (weights + kv) * _OVERHEAD + _CUDA_CONTEXT_GIB
    headroom = available_gib - required

    notes: list[str] = []
    if spec.notes:
        notes.append(spec.notes)
    if context > spec.context_max:
        notes.append(
            f"Contexto {context} supera el máximo del modelo ({spec.context_max})."
        )
    if 0 <= headroom < available_gib * 0.10:
        notes.append("Margen <10%: arriesgado bajo carga. Considera más cuantización o menos contexto.")

    return CompatibilityResult(
        model_id=spec.id,
        quant=quant,
        context=context,
        batch=batch,
        required_gib=round(required, 1),
        available_gib=round(available_gib, 1),
        weights_gib=round(weights, 1),
        kv_cache_gib=round(kv, 1),
        fits=headroom >= 0,
        headroom_gib=round(headroom, 1),
        runtimes=runtimes_for_quant(quant),
        notes=notes,
    )


def recommend_quant(
    spec: ModelSpec,
    available_gib: float,
    context: int | None = None,
    batch: int = 1,
    min_headroom_pct: float = 0.10,
) -> CompatibilityResult | None:
    """Mejor cuantización (más calidad) que entra dejando margen. None si nada cabe."""
    for quant in QUANT_PREFERENCE:
        res = check_fit(spec, available_gib, quant, context, batch)
        if res.fits and res.headroom_gib >= available_gib * min_headroom_pct:
            return res
    return None
