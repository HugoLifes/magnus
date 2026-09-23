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

from core.hardware import GPU
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


def ollama_required_gib(download_size_gib: float) -> float:
    """Memoria que ocupa un modelo de Ollama cargado, a partir de su descarga.

    El archivo GGUF ya viene cuantizado, así que los pesos ≈ el tamaño del
    archivo; encima van el grafo de cómputo y la KV cache del contexto por
    defecto (2–4 k tokens). Medido en el Jetson: qwen2.5:1.5b pesa 0.92 GiB y
    Ollama reservó 1.74 GiB (pesos 935 MiB + grafo 482 MiB + KV 56 MiB + CUDA).
    Con 1.2× + 0.7 GiB da 1.8.
    """
    return round(download_size_gib * 1.2 + 0.7, 1)


# En memoria unificada, además de lo que estima Ollama, la carga necesita el
# contexto CUDA y las páginas que el kernel se reserva. Medido en el Jetson: con
# ~2.1 GiB libres para una carga estimada en 1.9 GiB entraron los pesos (935 MiB)
# y falló el búfer de cómputo (300 MiB).
UNIFIED_CUDA_HEADROOM_GIB = 0.6


def load_memory_verdict(
    download_size_gib: float | None, gpu: GPU | None
) -> tuple[bool, str | None]:
    """¿Se puede cargar sin riesgo? (permitido, aviso).

    - Memoria unificada (Jetson, Spark, laptops N1X): si no cabe en la memoria
      LIBRE se niega, porque el sistema entero se queda sin RAM y se cuelga.
    - GPU dedicada: se permite siempre — Ollama manda las capas que no caben a
      la CPU —, pero se avisa de que irá mucho más lento.
    """
    if download_size_gib is None or gpu is None:
        return True, None
    needed = ollama_required_gib(download_size_gib)
    if gpu.unified_memory:
        with_cuda = round(needed + UNIFIED_CUDA_HEADROOM_GIB, 1)
        if with_cuda > gpu.free_gib:
            return False, (
                f"No hay memoria libre suficiente: el modelo necesita ~{with_cuda} GiB con CUDA "
                f"y hay {gpu.free_gib} GiB libres. Con memoria unificada cargarlo puede colgar "
                "el equipo. Cierra aplicaciones o elige un modelo más pequeño (magnus catalog)."
            )
        return True, None
    if needed > gpu.total_gib:
        return True, (
            f"El modelo (~{needed} GiB) no cabe entero en la VRAM ({gpu.total_gib} GiB): "
            "Ollama pondrá capas en la CPU y responderá mucho más lento."
        )
    return True, None


def unified_memory_note(res: CompatibilityResult, free_gib: float) -> str | None:
    """Aviso cuando el destino tiene memoria unificada (Jetson, DGX Spark).

    Ahí `available_gib` es la RAM total, pero la comparten el SO y los demás
    procesos. Medido en un Orin Nano con otro contenedor corriendo: 7.4 GiB
    totales y solo 2.8 GiB libres — un llama-3.1-8b q4 (6.1 GiB) "entra" sobre
    el total y colgaría el equipo entero al cargarlo.
    """
    if res.required_gib <= free_gib:
        return None
    return (
        f"Memoria unificada: el modelo necesita {res.required_gib} GiB y ahora hay "
        f"{free_gib} GiB libres (el resto lo usan el SO y otros procesos). "
        "Cargarlo puede colgar el equipo."
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


def quant_matrix(
    spec: ModelSpec,
    available_gib: float,
    context: int | None = None,
    batch: int = 1,
) -> list[CompatibilityResult]:
    """Analiza TODAS las cuantizaciones soportadas en un destino.

    Devuelve un resultado por cada cuant de `QUANT_PREFERENCE`, de mayor a menor
    calidad, para responder "¿qué cuantizaciones acepta este modelo aquí?".
    """
    return [check_fit(spec, available_gib, q, context, batch) for q in QUANT_PREFERENCE]
