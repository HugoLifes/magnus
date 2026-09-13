"""API local de Magnus.

Contrato único para la CLI y los clientes Flutter:

- Hardware y plataforma: /health /hardware /platform /system /compatibility
- Modelos: /catalog /models /models/local /models/loaded, descarga con progreso,
  carga con guarda de memoria, liberación y borrado
- Chat + medidor: WebSocket /chat, POST /chat, /conversations, /usage
- Ajustes: /settings

Skills, memoria/RAG y agentes se añaden encima de ESTA misma app, sin romper el
contrato. Ver docs/AGENT_HANDOFF.md y docs/BETA.md.

Arranque:  magnus serve     (o)     uvicorn daemon.app:api --port 8420
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool

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
    unified_memory_note,
)
from core.catalog import recommend, usable_gib
from core.chat import ChatError, ChatService, OllamaChatClient
from core.config import Settings, data_dir, load_settings, save_settings
from core.model_registry import MODEL_REGISTRY
from core.platform import detect_platform
from core.store import Store
from core.telemetry import sample_system

api = FastAPI(
    title="Magnus daemon",
    version="0.1.0",
    description="API local. Contrato único para CLI y clientes Flutter.",
)


# ---------------------------------------------------------------------------
# Dependencias (sustituibles en tests con api.dependency_overrides)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store(data_dir() / "magnus.db")


@lru_cache(maxsize=1)
def get_runtime_manager() -> RuntimeManager:
    return RuntimeManager(ollama_url=get_settings().ollama_url)


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    settings = get_settings()
    return ChatService(
        store=get_store(),
        settings=settings,
        platform=detect_platform(),
        client=OllamaChatClient(settings.ollama_url),
        power_sampler=lambda: sample_system().power_w,
        ensure_loaded=get_runtime_manager().ensure_loaded,
    )


StoreDep = Annotated[Store, Depends(get_store)]
ManagerDep = Annotated[RuntimeManager, Depends(get_runtime_manager)]
ChatDep = Annotated[ChatService, Depends(get_chat_service)]


# ---------------------------------------------------------------------------
# Hardware y plataforma
# ---------------------------------------------------------------------------


@api.get("/health")
def health(manager: ManagerDep) -> dict:
    return {
        "status": "ok",
        "service": "magnus",
        "version": "0.1.0",
        "ollama": manager.ollama_available(),
        "ollama_version": manager.ollama_version(),
    }


@api.get("/hardware")
def hardware() -> dict:
    return {"gpus": [g.__dict__ for g in detect_gpus()]}


@api.get("/platform")
def platform() -> dict:
    """Familia NVIDIA de esta máquina y cómo conviene servir modelos en ella."""
    return detect_platform().to_dict()


@api.get("/system")
def system() -> dict:
    """Muestra en vivo: uso de GPU, potencia (W), temperatura y memoria."""
    return sample_system().to_dict()


class CompatibilityRequest(BaseModel):
    model: str
    target: str = "auto"          # preset, GiB, o 'auto'
    quant: str = "fp16"
    context: int | None = None
    batch: int = 1


@api.post("/compatibility")
def compatibility(req: CompatibilityRequest) -> dict:
    """Veredicto de si un modelo entra en un destino. Núcleo de la decisión de montaje."""
    try:
        spec = get_model(req.model)
        vram = resolve_target_vram_gb(req.target)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    res = check_fit(spec, vram, quant=req.quant, context=req.context, batch=req.batch)
    if req.target == "auto":
        gpus = detect_gpus()
        if gpus and gpus[0].unified_memory:
            note = unified_memory_note(res, gpus[0].free_gib)
            if note:
                res.notes.append(note)
    payload = res.__dict__ | {"runtimes": [rt.value for rt in res.runtimes]}

    if not res.fits:
        rec = recommend_quant(spec, vram, context=req.context, batch=req.batch)
        payload["recommended_quant"] = rec.quant if rec else None
    return payload


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


@api.get("/models")
def models() -> dict:
    return {"models": [s.__dict__ for s in MODEL_REGISTRY.values()]}


@api.get("/catalog")
def catalog(capability: str | None = None) -> dict:
    """Modelos recomendados para ESTA máquina, con veredicto de si caben."""
    gpus = detect_gpus()
    profile = detect_platform(gpus)
    gpu = gpus[0] if gpus else None
    return {
        "family": profile.family.value,
        "usable_gib": usable_gib(profile, gpu),
        "models": [r.to_dict() for r in recommend(profile, gpu, capability)],
    }


@api.get("/models/local")
def models_local(manager: ManagerDep) -> dict:
    """Modelos descargados en el runtime, con tamaño y cuantización."""
    return {"models": [m.to_dict() for m in manager.list_local_models()]}


@api.get("/models/loaded")
def models_loaded(manager: ManagerDep) -> dict:
    """Modelos cargados ahora mismo en VRAM."""
    return {"loaded": [_loaded_model_to_dict(m) for m in manager.list_loaded()]}


class LoadRequest(BaseModel):
    backend: str = "ollama"
    pull_if_missing: bool = True
    # Cargar aunque la guarda de memoria lo desaconseje.
    force: bool = False


class UnloadRequest(BaseModel):
    backend: str = "ollama"
    delete_local: bool = False


def _loaded_model_to_dict(m: LoadedModel) -> dict:
    return {
        "model_id": m.model_id,
        "backend": m.backend.value,
        "size_vram_gib": m.size_vram_gib,
        "notes": m.notes,
    }


def _backend(name: str) -> RuntimeBackend:
    try:
        return RuntimeBackend(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Backend desconocido: {name!r}") from exc


@api.post("/models/{model_id:path}/load")
def model_load(model_id: str, manager: ManagerDep, req: LoadRequest | None = None) -> dict:
    """Carga un modelo. Si no está, lo descarga. En memoria unificada se niega si no cabe."""
    req = req or LoadRequest()
    try:
        loaded = manager.serve(model_id, backend=_backend(req.backend),
                               pull_if_missing=req.pull_if_missing, force=req.force)
    except RuntimeManagerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _loaded_model_to_dict(loaded)


@api.post("/models/{model_id:path}/unload")
def model_unload(model_id: str, manager: ManagerDep, req: UnloadRequest | None = None) -> dict:
    """Libera un modelo de VRAM (y opcionalmente del disco)."""
    req = req or UnloadRequest()
    try:
        manager.stop(model_id, backend=_backend(req.backend), delete_local=req.delete_local)
    except RuntimeManagerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"unloaded": model_id}


@api.post("/models/{model_id:path}/pull")
def model_pull(model_id: str, manager: ManagerDep) -> StreamingResponse:
    """Descarga con progreso: NDJSON, un objeto por línea.

    `{"status", "digest", "completed", "total", "percent"}`; termina con
    `status: "success"` o `status: "error"` con `detail`.
    """
    if not manager.ollama_available():
        raise HTTPException(status_code=503, detail="Ollama no está disponible.")

    def lines() -> Iterator[bytes]:
        try:
            for event in manager.pull(model_id):
                yield (json.dumps(event) + "\n").encode()
        except RuntimeManagerError as exc:
            yield (json.dumps({"status": "error", "detail": str(exc)}) + "\n").encode()

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@api.delete("/models/{model_id:path}")
def model_delete(model_id: str, manager: ManagerDep) -> dict:
    """Borra un modelo del disco."""
    try:
        manager.delete(model_id)
    except RuntimeManagerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"deleted": model_id}


# ---------------------------------------------------------------------------
# Chat + medidor
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    model: str
    message: str
    conversation_id: str | None = None
    system: str | None = None
    options: dict[str, Any] | None = None


@api.websocket("/chat")
async def chat_ws(websocket: WebSocket, service: ChatDep) -> None:
    """Chat con tokens en vivo.

    El cliente manda `{"model", "message", "conversation_id"?, "system"?}` por
    turno y recibe `start`, muchos `token` y un `done` con las métricas del
    turno (o `error`). La conexión sirve para varios turnos seguidos.
    """
    await websocket.accept()
    try:
        while True:
            try:
                req = ChatRequest.model_validate(await websocket.receive_json())
            except ValueError:
                await websocket.send_json(
                    {"type": "error", "detail": "Cada turno necesita 'model' y 'message'."}
                )
                continue
            events = service.stream(
                model=req.model, message=req.message, conversation_id=req.conversation_id,
                system=req.system, options=req.options,
            )
            try:
                async for event in iterate_in_threadpool(events):
                    await websocket.send_json(event)
            except ChatError as exc:
                await websocket.send_json({"type": "error", "detail": str(exc)})
    except WebSocketDisconnect:
        return


@api.post("/chat")
def chat_once(req: ChatRequest, service: ChatDep) -> dict:
    """Un turno sin streaming: devuelve la respuesta completa con sus métricas."""
    try:
        events = list(service.stream(
            model=req.model, message=req.message, conversation_id=req.conversation_id,
            system=req.system, options=req.options,
        ))
    except ChatError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return events[-1]


@api.get("/conversations")
def conversations(store: StoreDep, limit: int = 100) -> dict:
    return {"conversations": [c.to_dict() for c in store.list_conversations(limit)]}


@api.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str, store: StoreDep) -> dict:
    conv = store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return {
        "conversation": conv.to_dict(),
        "messages": [m.to_dict() for m in store.messages(conversation_id)],
    }


@api.delete("/conversations/{conversation_id}")
def conversation_delete(conversation_id: str, store: StoreDep) -> dict:
    if not store.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return {"deleted": conversation_id}


@api.get("/usage")
def usage(store: StoreDep, since: float | None = None) -> dict:
    """Totales del medidor: tokens, energía, coste local, coste nube y ahorro."""
    return store.usage_summary(since)


# ---------------------------------------------------------------------------
# Ajustes
# ---------------------------------------------------------------------------


@api.get("/settings")
def settings_get() -> dict:
    return get_settings().to_dict()


@api.put("/settings")
def settings_put(changes: dict[str, Any]) -> dict:
    try:
        updated = save_settings(changes, data_dir())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Los servicios leen los ajustes al crearse: se reconstruyen con los nuevos.
    get_settings.cache_clear()
    get_runtime_manager.cache_clear()
    get_chat_service.cache_clear()
    return updated.to_dict()
