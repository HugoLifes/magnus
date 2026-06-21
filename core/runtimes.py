"""Abstracción de runtimes de inferencia y qué cuantizaciones soporta cada uno.

Magnus no implementa inferencia: orquesta runtimes existentes. La elección del
runtime depende del hardware y del objetivo:

- ollama   -> simple, ideal para 1 usuario / desarrollo. Desaprovecha un B200.
- vllm     -> continuous batching + paged attention. Backend PRINCIPAL en B200.
- trtllm   -> TensorRT-LLM, máximo rendimiento NVIDIA, más complejo de montar.
"""

from __future__ import annotations

from enum import Enum


class Runtime(str, Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"
    TRTLLM = "trtllm"


# Qué cuantizaciones expone de forma práctica cada runtime.
_RUNTIME_QUANTS: dict[Runtime, set[str]] = {
    Runtime.OLLAMA: {"q8", "q6", "q5", "q4"},          # GGUF
    Runtime.VLLM: {"fp16", "fp8", "q8", "q4"},          # awq/gptq/fp8
    Runtime.TRTLLM: {"fp16", "fp8", "q4"},
}

# Recomendación por perfil de uso.
RUNTIME_FOR_PROFILE: dict[str, Runtime] = {
    "dev": Runtime.OLLAMA,
    "single-user": Runtime.OLLAMA,
    "serving": Runtime.VLLM,
    "max-throughput": Runtime.TRTLLM,
}


def runtimes_for_quant(quant: str) -> list[Runtime]:
    """Runtimes capaces de correr una cuantización dada."""
    return [rt for rt, quants in _RUNTIME_QUANTS.items() if quant in quants]
