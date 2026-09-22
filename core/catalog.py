"""Catálogo curado de modelos de Ollama y recomendación según el hardware.

Quien estrena una laptop con RTX no sabe si le cabe `qwen3:14b`. El catálogo
lleva el tamaño de descarga de cada etiqueta (cuantización por defecto de
Ollama, q4_K_M) y lo cruza con la memoria real de la máquina.

Los tamaños son los de la biblioteca de Ollama pasados a GiB y redondeados: son
para decidir, no para reservar. El tamaño exacto queda en `/api/tags` tras
descargar, y es el que usa la guarda de memoria al cargar.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from core.compatibility import UNIFIED_CUDA_HEADROOM_GIB, ollama_required_gib
from core.hardware import GPU
from core.platform import PlatformProfile

CHAT = "chat"
CODE = "code"
REASONING = "reasoning"
VISION = "vision"
TOOLS = "tools"
EMBEDDING = "embedding"


@dataclass(frozen=True)
class CatalogModel:
    id: str                      # etiqueta de Ollama
    name: str
    params_b: float
    size_gib: float              # descarga
    capabilities: tuple[str, ...]
    context: int
    license: str
    description: str

    def to_dict(self) -> dict:
        return asdict(self) | {"capabilities": list(self.capabilities)}


def _m(id_, name, params, size, caps, ctx, lic, desc) -> CatalogModel:
    return CatalogModel(id_, name, params, size, tuple(caps), ctx, lic, desc)


CATALOG: tuple[CatalogModel, ...] = (
    # --- Generalistas ---
    _m("qwen2.5:0.5b", "Qwen2.5 0.5B", 0.49, 0.37, [CHAT, TOOLS], 32768, "Apache-2.0",
       "El más pequeño con respuesta fluida; medido a 60 tok/s en un Jetson Orin Nano. "
       "Funciona con Ollama antiguo."),
    _m("qwen3:0.6b", "Qwen3 0.6B", 0.6, 0.5, [CHAT, TOOLS], 40960, "Apache-2.0",
       "Mínimo para probar; útil como enrutador o clasificador."),
    _m("qwen3:1.7b", "Qwen3 1.7B", 1.7, 1.3, [CHAT, TOOLS, REASONING], 40960, "Apache-2.0",
       "Cabe en un Jetson Orin Nano; razona y llama herramientas."),
    _m("qwen3:4b", "Qwen3 4B", 4.0, 2.3, [CHAT, TOOLS, REASONING], 40960, "Apache-2.0",
       "El mejor equilibrio para laptops de 4–6 GB."),
    _m("qwen3:8b", "Qwen3 8B", 8.2, 4.8, [CHAT, TOOLS, REASONING], 40960, "Apache-2.0",
       "Generalista sólido para RTX de 8 GB."),
    _m("qwen3:14b", "Qwen3 14B", 14.8, 8.7, [CHAT, TOOLS, REASONING], 40960, "Apache-2.0",
       "Para RTX de 12–16 GB."),
    _m("qwen3:30b", "Qwen3 30B-A3B", 30.5, 17.7, [CHAT, TOOLS, REASONING], 40960, "Apache-2.0",
       "MoE con 3 B activos: calidad de 30 B a velocidad de 3 B. RTX 4090/5090."),
    _m("qwen3:32b", "Qwen3 32B", 32.8, 18.6, [CHAT, TOOLS, REASONING], 40960, "Apache-2.0",
       "Denso, máxima calidad en 24 GB."),
    _m("llama3.2:1b", "Llama 3.2 1B", 1.2, 1.2, [CHAT, TOOLS], 131072, "Llama 3.2 Community",
       "Muy ligero, contexto largo."),
    _m("llama3.2:3b", "Llama 3.2 3B", 3.2, 1.9, [CHAT, TOOLS], 131072, "Llama 3.2 Community",
       "Ligero y conversacional."),
    _m("llama3.1:8b", "Llama 3.1 8B", 8.0, 4.6, [CHAT, TOOLS], 131072, "Llama 3.1 Community",
       "Clásico de 8 B, gran ecosistema."),
    _m("llama3.3:70b", "Llama 3.3 70B", 70.6, 40.0, [CHAT, TOOLS], 131072,
       "Llama 3.3 Community", "Nivel frontera en local: 48 GB+ o DGX Spark."),
    _m("gpt-oss:20b", "gpt-oss 20B", 20.9, 13.0, [CHAT, CODE, TOOLS, REASONING], 131072,
       "Apache-2.0",
       "Modelo abierto de OpenAI; razonamiento y herramientas en 16 GB."),
    _m("gpt-oss:120b", "gpt-oss 120B", 116.8, 60.5, [CHAT, TOOLS, REASONING], 131072,
       "Apache-2.0", "Para DGX Spark, RTX PRO 6000 o datacenter."),
    _m("phi4-mini:3.8b", "Phi-4 mini", 3.8, 2.3, [CHAT, TOOLS], 131072, "MIT",
       "Pequeño y bueno en instrucciones."),
    _m("phi4:14b", "Phi-4 14B", 14.7, 8.5, [CHAT, REASONING], 16384, "MIT",
       "Fuerte en matemáticas y lógica."),
    _m("mistral-small3.2:24b", "Mistral Small 3.2", 24.0, 14.0, [CHAT, TOOLS, VISION], 131072,
       "Apache-2.0", "Visión y herramientas en 16–24 GB."),
    # --- Razonamiento ---
    _m("deepseek-r1:1.5b", "DeepSeek-R1 1.5B", 1.8, 1.0, [CHAT, REASONING], 131072, "MIT",
       "Destilado pequeño que muestra su razonamiento."),
    _m("deepseek-r1:8b", "DeepSeek-R1 8B", 8.2, 4.8, [CHAT, REASONING], 131072, "MIT",
       "Razonamiento paso a paso en 8 GB."),
    _m("deepseek-r1:14b", "DeepSeek-R1 14B", 14.8, 8.4, [CHAT, REASONING], 131072, "MIT",
       "Razonamiento para 12–16 GB."),
    _m("deepseek-r1:32b", "DeepSeek-R1 32B", 32.8, 18.6, [CHAT, REASONING], 131072, "MIT",
       "Razonamiento de alta calidad en 24 GB."),
    # --- Código ---
    _m("qwen2.5-coder:1.5b", "Qwen2.5 Coder 1.5B", 1.5, 0.9, [CODE], 32768, "Apache-2.0",
       "Autocompletado de código muy rápido."),
    _m("qwen2.5-coder:7b", "Qwen2.5 Coder 7B", 7.6, 4.4, [CODE, TOOLS], 32768, "Apache-2.0",
       "Asistente de código para 8 GB."),
    _m("qwen2.5-coder:32b", "Qwen2.5 Coder 32B", 32.8, 18.6, [CODE, TOOLS], 32768, "Apache-2.0",
       "Código de primer nivel en 24 GB."),
    # --- Agentes de código (Magnus Code) ---
    # Para trabajar en un proyecto no basta con escribir código: hay que llamar
    # herramientas muchas veces seguidas y aguantar contextos largos. Estos son
    # los que lo hacen bien en 2026; ver docs/MAGNUS_CODE.md §8.
    _m("devstral:24b", "Devstral Small 24B", 23.6, 14.0, [CODE, TOOLS], 131072, "Apache-2.0",
       "Hecho para agentes de código: ediciones en varios archivos. Pide 16 GB."),
    _m("qwen3-coder:30b", "Qwen3-Coder 30B-A3B", 30.5, 19.0, [CODE, TOOLS], 262144, "Apache-2.0",
       "Mezcla de expertos: 3 B activos, rápido, 256K de contexto. Pide 24 GB."),
    # --- Visión ---
    _m("gemma3:4b", "Gemma 3 4B", 4.3, 3.1, [CHAT, VISION], 131072, "Gemma",
       "Entiende imágenes con poca memoria."),
    _m("gemma3:12b", "Gemma 3 12B", 12.2, 7.5, [CHAT, VISION], 131072, "Gemma",
       "Visión y chat para 12 GB."),
    _m("gemma3:27b", "Gemma 3 27B", 27.4, 15.8, [CHAT, VISION], 131072, "Gemma",
       "Visión de alta calidad en 24 GB."),
    # --- Embeddings (RAG) ---
    _m("nomic-embed-text", "Nomic Embed Text", 0.14, 0.26, [EMBEDDING], 8192, "Apache-2.0",
       "Embeddings para el RAG local; cabe en cualquier equipo."),
    _m("bge-m3", "BGE-M3", 0.57, 1.1, [EMBEDDING], 8192, "MIT",
       "Embeddings multilingües (bueno en español)."),
)

DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"


def get_catalog_model(model_id: str) -> CatalogModel | None:
    return next((m for m in CATALOG if m.id == model_id), None)


@dataclass(frozen=True)
class Recommendation:
    model: CatalogModel
    required_gib: float
    fits: bool
    note: str | None = None

    def to_dict(self) -> dict:
        return self.model.to_dict() | {
            "required_gib": self.required_gib, "fits": self.fits, "note": self.note,
        }


def usable_gib(profile: PlatformProfile, gpu: GPU | None, evictable_gib: float = 0.0) -> float:
    """Memoria con la que se puede contar para un modelo en esta máquina.

    `evictable_gib`: memoria de los modelos cargados que saldrían al cargar otro
    (en equipos de un solo modelo). Sin contarla, con qwen3:0.6b cargado el Jetson
    anunciaba "0 de 29 caben en 0.9 GiB".
    """
    if gpu is None:
        return 0.0
    if profile.unified_memory:
        # Lo libre ahora, sin pasar de lo que deja la reserva del sistema, menos la
        # holgura de CUDA: el mismo criterio con el que la guarda permite cargar.
        free = min(gpu.free_gib + evictable_gib, profile.total_memory_gib - profile.reserve_gib)
        return round(max(0.0, free - UNIFIED_CUDA_HEADROOM_GIB), 1)
    # GPU dedicada: el total (varias GPUs sumadas) menos el margen del escritorio.
    return round(max(0.0, profile.total_memory_gib - 1.0), 1)


def recommend(
    profile: PlatformProfile, gpu: GPU | None, capability: str | None = None,
    evictable_gib: float = 0.0,
) -> list[Recommendation]:
    """Catálogo con veredicto por modelo: primero lo que cabe, del más capaz al menor."""
    usable = usable_gib(profile, gpu, evictable_gib)
    recs = []
    for model in CATALOG:
        if capability and capability not in model.capabilities:
            continue
        required = ollama_required_gib(model.size_gib)
        fits = required <= usable
        note = None
        if not fits and not profile.unified_memory and required <= usable * 2:
            note = "Correría repartido entre GPU y CPU, bastante más lento."
        recs.append(Recommendation(model, required, fits, note))
    return sorted(recs, key=lambda r: (not r.fits, -r.model.params_b if r.fits else r.required_gib))


def evictable_gib(profile: PlatformProfile, loaded_sizes_gib: list[float | None]) -> float:
    """Memoria que liberaría Ollama al cargar otro modelo: solo si cabe uno a la vez."""
    if profile.max_loaded_models > 1:
        return 0.0
    return round(sum(s or 0.0 for s in loaded_sizes_gib), 2)


def best_fit(profile: PlatformProfile, gpu: GPU | None, capability: str = CHAT) -> CatalogModel | None:
    """El modelo más capaz de esa capacidad que cabe con holgura."""
    for rec in recommend(profile, gpu, capability):
        if rec.fits:
            return rec.model
    return None
