"""API local de Magnus.

Fase 0: solo lectura sobre `core` (hardware, modelos, compatibilidad).
Fase 1: runtime manager — load/unload/ps de modelos reales.

Las piezas con estado (skills, memoria/RAG, runtime de agentes, medidor de tokens) y
el WebSocket de chat en streaming se añaden encima de ESTA misma app, sin romper
el contrato. Ver docs/AGENT_HANDOFF.md.

Arranque:  magnus serve     (o)     uvicorn daemon.app:api --port 8420
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core import (
    LoadedModel,
    RuntimeBackend,
    RuntimeManager,
    RuntimeManagerError,
    check_fit,
    detect_gpus,
    get_model,
    recommend_quant,
    resolve_target_vram_gb,
)
from core.model_registry import MODEL_REGISTRY

api = FastAPI(
    title="Magnus daemon",
    version="0.1.0",
    description="API local. Contrato único para CLI y clientes Flutter.",
)

_OLLAMA_URL = os.environ.get("MAGNUS_OLLAMA_URL", "http://127.0.0.1:11434")
_runtime_manager = RuntimeManager(ollama_url=_OLLAMA_URL)


class CompatibilityRequest(BaseModel):
    model: str
    target: str = "auto"          # preset, GiB, o 'auto'
    quant: str = "fp16"
    context: int | None = None
    batch: int = 1


@api.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "magnus",
        "version": "0.1.0",
        "ollama": _runtime_manager.ollama_available(),
    }


# ---------------------------------------------------------------------------
# Runtime manager (Fase 1)
# ---------------------------------------------------------------------------


class LoadRequest(BaseModel):
    backend: str = "ollama"
    pull_if_missing: bool = True


class UnloadRequest(BaseModel):
    backend: str = "ollama"
    delete_local: bool = False


def _loaded_model_to_dict(m: LoadedModel) -> dict:
    return {
        "model_id": m.model_id,
        "backend": m.backend.value,
        "size_vram_gib": m.size_vram_gib,
    }


@api.get("/models/loaded")
def models_loaded() -> dict:
    """Modelos cargados ahora mismo en VRAM."""
    loaded = _runtime_manager.list_loaded()
    return {"loaded": [_loaded_model_to_dict(m) for m in loaded]}


@api.post("/models/{model_id:path}/load")
def model_load(model_id: str, req: LoadRequest = LoadRequest()) -> dict:
    """Carga un modelo en VRAM. Si no está en Ollama, lo descarga primero."""
    try:
        backend = RuntimeBackend(req.backend)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Backend desconocido: {req.backend!r}")
    try:
        loaded = _runtime_manager.serve(model_id, backend=backend, pull_if_missing=req.pull_if_missing)
    except RuntimeManagerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _loaded_model_to_dict(loaded)


@api.post("/models/{model_id:path}/unload")
def model_unload(model_id: str, req: UnloadRequest = UnloadRequest()) -> dict:
    """Libera un modelo de VRAM (y opcionalmente del disco)."""
    try:
        backend = RuntimeBackend(req.backend)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Backend desconocido: {req.backend!r}")
    try:
        _runtime_manager.stop(model_id, backend=backend, delete_local=req.delete_local)
    except RuntimeManagerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"unloaded": model_id}


@api.get("/hardware")
def hardware() -> dict:
    return {"gpus": [g.__dict__ for g in detect_gpus()]}


@api.get("/models")
def models() -> dict:
    return {"models": [s.__dict__ for s in MODEL_REGISTRY.values()]}


@api.post("/compatibility")
def compatibility(req: CompatibilityRequest) -> dict:
    """Veredicto de si un modelo entra en un destino. Núcleo de la decisión de montaje."""
    try:
        spec = get_model(req.model)
        vram = resolve_target_vram_gb(req.target)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    res = check_fit(spec, vram, quant=req.quant, context=req.context, batch=req.batch)
    payload = res.__dict__ | {"runtimes": [rt.value for rt in res.runtimes]}

    if not res.fits:
        rec = recommend_quant(spec, vram, context=req.context, batch=req.batch)
        payload["recommended_quant"] = rec.quant if rec else None
    return payload
