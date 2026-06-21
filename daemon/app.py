"""API local de Magnus.

Fase 0: solo lectura sobre `core` (hardware, modelos, compatibilidad). Las
piezas con estado (skills, memoria/RAG, runtime de agentes, medidor de tokens) y
el WebSocket de chat en streaming se añaden encima de ESTA misma app, sin romper
el contrato. Ver docs/AGENT_HANDOFF.md.

Arranque:  magnus serve     (o)     uvicorn daemon.app:api --port 8420
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core import (
    check_fit,
    detect_gpus,
    get_model,
    recommend_quant,
    resolve_target_vram_gb,
)
from core.model_registry import MODEL_REGISTRY

api = FastAPI(
    title="Magnus daemon",
    version="0.0.1",
    description="API local. Contrato único para CLI y clientes Flutter.",
)


class CompatibilityRequest(BaseModel):
    model: str
    target: str = "auto"          # preset, GiB, o 'auto'
    quant: str = "fp16"
    context: int | None = None
    batch: int = 1


@api.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "magnus", "version": "0.0.1"}


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
