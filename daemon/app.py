"""API local de Magnus.

Contrato único para la CLI y los clientes Flutter:

- Hardware y plataforma: /health /hardware /platform /system /compatibility
- Modelos: /catalog /models /models/local /models/loaded, descarga con progreso,
  carga con guarda de memoria, liberación y borrado
- Chat + medidor: WebSocket /chat, POST /chat, /conversations, /usage
- Skills: /skills
- Documentos y memoria: /rag/*, /memory
- Proveedores externos (vLLM en la red, APIs con clave del usuario): /providers
- Ajustes: /settings

El runtime de agentes se añade encima de ESTA misma app, sin romper el contrato.
Ver docs/AGENT_HANDOFF.md y docs/BETA.md.

Arranque:  magnus serve     (o)     uvicorn daemon.app:api --port 8420
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
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
from core.agent import (
    BUILTIN_AGENTS_DIR,
    TOOLS,
    AgentError,
    AgentRegistry,
    AgentRunner,
    build_agent,
)
from core.catalog import evictable_gib, recommend, usable_gib
from core.chat import ChatError, ChatService, OllamaChatClient
from core.config import Settings, data_dir, load_settings, save_settings
from core.license import (
    GRACE_DAYS,
    License,
    LicenseError,
    LicenseStore,
    plan_allows,
)
from core.messages import MessagesProxy, ProxyError
from core.model_registry import MODEL_REGISTRY
from core.persona import list_personas
from core.platform import detect_platform
from core.providers import PRESETS, Provider, ProviderError, ProviderKind, ProviderRegistry
from core.rag import (
    DEFAULT_CHUNK_CHARS,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_OVERLAP_CHARS,
    OllamaEmbedder,
    RagError,
    RagStore,
)
from core.secrets import SecretStore
from core.security import PUBLIC_PATHS, token_ok
from core.skills import BUILTIN_SKILLS_DIR, SkillError, SkillRegistry, build_skill
from core.store import Store
from core.telemetry import sample_system

api = FastAPI(
    title="Magnus daemon",
    version="0.9.0b1",
    description="API local. Contrato único para CLI y clientes Flutter.",
)


# ---------------------------------------------------------------------------
# Dependencias (sustituibles en tests con api.dependency_overrides)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@api.middleware("http")
async def require_token(request: Request, call_next):
    """Con token configurado, todo salvo /health lo exige (ver core/security.py)."""
    if request.url.path not in PUBLIC_PATHS and not token_ok(
        get_settings().api_token, request.headers, request.query_params
    ):
        return JSONResponse(status_code=401,
                            content={"detail": "Falta el token de acceso o no es válido."})
    return await call_next(request)


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store(data_dir() / "magnus.db")


@lru_cache(maxsize=1)
def get_runtime_manager() -> RuntimeManager:
    return RuntimeManager(ollama_url=get_settings().ollama_url)


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry(data_dir() / "skills", BUILTIN_SKILLS_DIR)


@lru_cache(maxsize=1)
def get_rag_store() -> RagStore:
    url = get_settings().ollama_url
    manager = get_runtime_manager()
    return RagStore(
        data_dir() / "magnus.db",
        lambda model: OllamaEmbedder(url, model, before=manager.ensure_loaded),
    )


@lru_cache(maxsize=1)
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry(data_dir(), SecretStore(data_dir()))


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
        skills=get_skill_registry(),
        rag=get_rag_store(),
        remote=get_provider_registry().client,
    )


@lru_cache(maxsize=1)
def get_license_store() -> LicenseStore:
    return LicenseStore(data_dir())


@lru_cache(maxsize=1)
def get_messages_proxy() -> MessagesProxy:
    settings = get_settings()
    return MessagesProxy(
        manager=get_runtime_manager(),
        store=get_store(),
        settings=settings,
        platform=detect_platform(),
        ollama_url=settings.ollama_url,
        power_sampler=lambda: sample_system().power_w,
    )


@lru_cache(maxsize=1)
def get_agent_registry() -> AgentRegistry:
    return AgentRegistry(data_dir() / "agents", BUILTIN_AGENTS_DIR)


@lru_cache(maxsize=1)
def get_agent_runner() -> AgentRunner:
    settings = get_settings()
    return AgentRunner(
        store=get_store(),
        settings=settings,
        platform=detect_platform(),
        client=OllamaChatClient(settings.ollama_url),
        power_sampler=lambda: sample_system().power_w,
        ensure_loaded=get_runtime_manager().ensure_loaded,
        skills=get_skill_registry(),
        rag=get_rag_store(),
    )


StoreDep = Annotated[Store, Depends(get_store)]
LicenseDep = Annotated[LicenseStore, Depends(get_license_store)]
MessagesDep = Annotated[MessagesProxy, Depends(get_messages_proxy)]
ManagerDep = Annotated[RuntimeManager, Depends(get_runtime_manager)]
ChatDep = Annotated[ChatService, Depends(get_chat_service)]
SkillsDep = Annotated[SkillRegistry, Depends(get_skill_registry)]
RagDep = Annotated[RagStore, Depends(get_rag_store)]
AgentsDep = Annotated[AgentRegistry, Depends(get_agent_registry)]
RunnerDep = Annotated[AgentRunner, Depends(get_agent_runner)]
ProvidersDep = Annotated[ProviderRegistry, Depends(get_provider_registry)]


# ---------------------------------------------------------------------------
# Agentes (Fase 1.5)
# ---------------------------------------------------------------------------


class AgentBody(BaseModel):
    description: str
    system: str = ""
    model: str | None = None
    skills: list[str] = []
    tools: list[str] = []
    collection: str | None = None
    max_steps: int = 6
    max_output_tokens: int = 4000
    think: bool | None = None


class AgentRunRequest(BaseModel):
    message: str
    model: str | None = None
    conversation_id: str | None = None


@api.get("/tools")
def tools_list() -> dict:
    """Herramientas que un agente puede usar. Todas incluidas y seguras."""
    return {"tools": [{"name": t.name, "description": t.description} for t in TOOLS.values()]}


@api.get("/agents")
def agents_list(registry: AgentsDep) -> dict:
    return {"agents": [a.to_dict() for a in registry.list()], "errors": registry.errors}


@api.get("/agents/{name}")
def agent_detail(name: str, registry: AgentsDep) -> dict:
    spec = registry.get(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"No existe el agente '{name}'.")
    return spec.to_dict()


@api.put("/agents/{name}")
def agent_put(name: str, req: AgentBody, registry: AgentsDep) -> dict:
    """Crea o reemplaza un agente del usuario."""
    try:
        return registry.save(build_agent({"name": name, **req.model_dump()})).to_dict()
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.delete("/agents/{name}")
def agent_delete(name: str, registry: AgentsDep) -> dict:
    try:
        deleted = registry.delete(name)
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No existe el agente '{name}'.")
    return {"deleted": name}


@api.post("/agents/{name}/run")
def agent_run(name: str, req: AgentRunRequest, registry: AgentsDep,
              runner: RunnerDep) -> StreamingResponse:
    """Ejecuta un agente. NDJSON: start, tool_call, tool_result, answer, done (o error)."""
    spec = registry.get(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"No existe el agente '{name}'.")

    def lines() -> Iterator[bytes]:
        try:
            for event in runner.run(spec, req.message, model=req.model,
                                    conversation_id=req.conversation_id):
                yield (json.dumps(event, ensure_ascii=False) + "\n").encode()
        except AgentError as exc:
            yield (json.dumps({"type": "error", "detail": str(exc)},
                              ensure_ascii=False) + "\n").encode()

    return StreamingResponse(lines(), media_type="application/x-ndjson")


# ---------------------------------------------------------------------------
# Hardware y plataforma
# ---------------------------------------------------------------------------


@api.get("/health")
def health(manager: ManagerDep) -> dict:
    # Un solo sondeo: la versión ya dice si Ollama responde.
    ollama_version = manager.ollama_version()
    return {
        "status": "ok",
        "service": "magnus",
        "version": "0.9.0b1",
        "ollama": ollama_version is not None,
        "ollama_version": ollama_version,
    }


class LicenseRequest(BaseModel):
    text: str


def _license_payload(lic: License) -> dict:
    """Lo que ve la app: la licencia y qué desbloquea."""
    plan = lic.effective_plan()
    return {
        "license": lic.to_dict(),
        "grace_days": GRACE_DAYS,
        "features": {
            "rag_pro": plan_allows(plan, "pro"),
            "code_autonomous": plan_allows(plan, "pro"),
            "team_audit": plan_allows(plan, "team"),
        },
    }


@api.get("/personas")
def personas() -> dict:
    """Personalidades disponibles para el chat (cómo habla Magnus)."""
    return {"personas": list_personas()}


@api.get("/license")
def license_show(licenses: LicenseDep) -> dict:
    """Plan activo de este equipo. Sin licencia, Community."""
    return _license_payload(licenses.current())


@api.post("/license")
def license_activate(req: LicenseRequest, licenses: LicenseDep) -> dict:
    """Activa una licencia firmada. No sale a internet."""
    try:
        return _license_payload(licenses.activate(req.text))
    except LicenseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.delete("/license")
def license_deactivate(licenses: LicenseDep) -> dict:
    """Quita la licencia de este equipo y vuelve a Community."""
    licenses.deactivate()
    return _license_payload(licenses.current())


@api.post("/v1/messages")
async def anthropic_messages(request: Request, proxy: MessagesDep):
    """API de mensajes de Anthropic sobre los modelos de este equipo.

    Es lo que hace que Claude Code, Codex CLI, OpenCode o Aider corran contra la
    GPU local: eligen modelo de la nube, Magnus lo traduce al mejor modelo de
    código descargado, vigila la memoria y mide el turno.
    """
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="El cuerpo no es JSON.") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="El cuerpo debe ser un objeto JSON.")

    try:
        if body.get("stream"):
            # El primer evento se pide aquí para que un fallo salga como error
            # HTTP y no como un flujo a medias.
            events = proxy.stream(body)
            first = next(events)

            def forward():
                yield first
                yield from events

            return StreamingResponse(forward(), media_type="text/event-stream")
        turn = proxy.complete(body)
    except ProxyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StopIteration as exc:  # el runtime cerró sin mandar nada
        raise HTTPException(status_code=502, detail="El runtime no respondió.") from exc
    return JSONResponse(turn.payload)


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
def catalog(manager: ManagerDep, capability: str | None = None) -> dict:
    """Modelos recomendados para ESTA máquina, con veredicto de si caben."""
    gpus = detect_gpus()
    profile = detect_platform(gpus)
    gpu = gpus[0] if gpus else None
    # Donde cabe un solo modelo, el cargado saldría al cargar otro: su memoria cuenta.
    evictable = evictable_gib(profile, [m.size_vram_gib for m in manager.list_loaded()])
    return {
        "family": profile.family.value,
        "usable_gib": usable_gib(profile, gpu, evictable),
        "models": [r.to_dict() for r in recommend(profile, gpu, capability, evictable)],
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
    # Colección de documentos en la que buscar antes de responder.
    collection: str | None = None
    # None: automático (activa donde caben varios modelos a la vez).
    use_memory: bool | None = None
    rag_k: int = 4
    # Razonamiento en modelos que razonan (qwen3, deepseek-r1). None: el del modelo.
    think: bool | None = None
    # Dónde correr el turno: None o "local" = este equipo; si no, el id de un
    # proveedor de /providers. Nunca se elige solo.
    provider: str | None = None
    # Cómo habla Magnus en este turno. None: la de Ajustes (ver /personas).
    persona: str | None = None


def _stream_chat(service: ChatService, req: ChatRequest) -> Iterator[dict]:
    return service.stream(
        model=req.model, message=req.message, conversation_id=req.conversation_id,
        system=req.system, options=req.options, collection=req.collection,
        use_memory=req.use_memory, rag_k=req.rag_k, think=req.think,
        provider=req.provider, persona=req.persona,
    )


@api.websocket("/chat")
async def chat_ws(websocket: WebSocket, service: ChatDep) -> None:
    """Chat con tokens en vivo.

    El cliente manda un `ChatRequest` por turno y recibe `start` (con skills y
    fuentes), muchos `token` y un `done` con las métricas del turno (o `error`).
    La conexión sirve para varios turnos seguidos.
    """
    # El middleware HTTP no cubre WebSockets: se comprueba aquí, antes de aceptar.
    if not token_ok(get_settings().api_token, websocket.headers, websocket.query_params):
        await websocket.close(code=4401)
        return
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
            try:
                async for event in iterate_in_threadpool(_stream_chat(service, req)):
                    await websocket.send_json(event)
            except ChatError as exc:
                await websocket.send_json({"type": "error", "detail": str(exc)})
    except WebSocketDisconnect:
        return


@api.post("/chat")
def chat_once(req: ChatRequest, service: ChatDep) -> dict:
    """Un turno sin streaming: devuelve la respuesta completa con sus métricas."""
    try:
        events = list(_stream_chat(service, req))
    except ChatError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    done = events[-1]
    done["skills"] = events[0].get("skills", [])
    done["sources"] = events[0].get("sources", [])
    return done


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
# Skills
# ---------------------------------------------------------------------------


class SkillBody(BaseModel):
    description: str
    body: str
    triggers: list[str] = []
    tools: list[str] = []


class ResolveRequest(BaseModel):
    message: str


@api.get("/skills")
def skills_list(registry: SkillsDep) -> dict:
    """Skills disponibles (incluidas y del usuario) y las que tienen errores."""
    return {
        "skills": [s.to_dict(include_body=False) for s in registry.list()],
        "errors": registry.errors,
    }


@api.get("/skills/{name}")
def skill_detail(name: str, registry: SkillsDep) -> dict:
    skill = registry.get(name)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"No existe la skill '{name}'.")
    return skill.to_dict()


@api.put("/skills/{name}")
def skill_put(name: str, req: SkillBody, registry: SkillsDep) -> dict:
    """Crea o reemplaza una skill del usuario. Surte efecto en el siguiente mensaje."""
    try:
        skill = build_skill(name, req.description, req.body, req.triggers, req.tools)
        return registry.save(skill).to_dict()
    except SkillError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.delete("/skills/{name}")
def skill_delete(name: str, registry: SkillsDep) -> dict:
    try:
        deleted = registry.delete(name)
    except SkillError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No existe la skill '{name}'.")
    return {"deleted": name}


@api.post("/skills/reload")
def skills_reload(registry: SkillsDep) -> dict:
    """Relee las skills del disco (también ocurre solo al detectar cambios)."""
    errors = registry.reload()
    return {"skills": [s.name for s in registry.list()], "errors": errors}


@api.post("/skills/resolve")
def skills_resolve(req: ResolveRequest, registry: SkillsDep) -> dict:
    """Qué skills se aplicarían a un mensaje, sin mandarlo al modelo."""
    return {"skills": [s.name for s in registry.resolve(req.message)]}


# ---------------------------------------------------------------------------
# Documentos (RAG) y memoria
# ---------------------------------------------------------------------------


class CollectionRequest(BaseModel):
    name: str
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    chunk_chars: int = DEFAULT_CHUNK_CHARS
    overlap_chars: int = DEFAULT_OVERLAP_CHARS


class IngestRequest(BaseModel):
    collection: str
    # Archivos o carpetas de ESTA máquina (el daemon los lee; por defecto solo
    # escucha en loopback).
    paths: list[str] = []
    # O texto directo, p. ej. pegado desde el cliente.
    text: str | None = None
    source: str = "texto pegado"


class SearchRequest(BaseModel):
    collection: str
    query: str
    k: int = 5


class MemoryRequest(BaseModel):
    text: str


class MemorySearchRequest(BaseModel):
    query: str
    k: int = 5


def _rag_call(fn):
    try:
        return fn()
    except RagError as exc:
        status = 404 if str(exc).startswith("No existe") else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@api.get("/rag/collections")
def rag_collections(store: RagDep) -> dict:
    return {"collections": [c.to_dict() for c in store.list_collections()]}


@api.post("/rag/collections")
def rag_collection_create(req: CollectionRequest, store: RagDep) -> dict:
    return _rag_call(lambda: store.create_collection(
        req.name, req.embedding_model, req.chunk_chars, req.overlap_chars).to_dict())


@api.delete("/rag/collections/{name}")
def rag_collection_delete(name: str, store: RagDep) -> dict:
    _rag_call(lambda: store.delete_collection(name))
    return {"deleted": name}


@api.get("/rag/collections/{name}/documents")
def rag_documents(name: str, store: RagDep) -> dict:
    return {"documents": _rag_call(lambda: store.list_documents(name))}


@api.delete("/rag/collections/{name}/documents/{document_id}")
def rag_document_delete(name: str, document_id: str, store: RagDep) -> dict:
    if not _rag_call(lambda: store.delete_document(name, document_id)):
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return {"deleted": document_id}


@api.post("/rag/ingest")
def rag_ingest(req: IngestRequest, store: RagDep) -> dict:
    """Indexa archivos/carpetas locales o un texto. Calcula embeddings: puede tardar."""
    if not req.paths and not req.text:
        raise HTTPException(status_code=400, detail="Indica 'paths' o 'text'.")
    result: dict = {"indexed": 0, "skipped": 0, "chunks": 0, "errors": {}}
    if req.text:
        r = _rag_call(lambda: store.ingest_text(req.collection, req.text, req.source))
        result["skipped" if r["skipped"] else "indexed"] += 1
        result["chunks"] += r["chunks"]
    for path in req.paths:
        r = _rag_call(lambda p=path: store.ingest_path(req.collection, Path(p)))
        for key in ("indexed", "skipped", "chunks"):
            result[key] += r[key]
        result["errors"].update(r["errors"])
    return result


@api.post("/rag/search")
def rag_search(req: SearchRequest, store: RagDep) -> dict:
    hits = _rag_call(lambda: store.search(req.collection, req.query, req.k))
    return {"hits": [h.to_dict() for h in hits]}


@api.get("/memory")
def memory_list(store: RagDep) -> dict:
    return {"memories": [m.to_dict() for m in store.list_memories()]}


@api.post("/memory")
def memory_add(req: MemoryRequest, store: RagDep) -> dict:
    return _rag_call(lambda: store.add_memory(req.text)).to_dict()


@api.delete("/memory/{memory_id}")
def memory_delete(memory_id: int, store: RagDep) -> dict:
    if not store.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Memoria no encontrada.")
    return {"deleted": memory_id}


@api.post("/memory/search")
def memory_search(req: MemorySearchRequest, store: RagDep) -> dict:
    hits = _rag_call(lambda: store.search_memories(req.query, req.k))
    return {"memories": [m.to_dict() for m in hits]}


# ---------------------------------------------------------------------------
# Proveedores externos
# ---------------------------------------------------------------------------


class ProviderBody(BaseModel):
    kind: str
    name: str | None = None
    base_url: str | None = None
    # Solo de ida: nunca se devuelve. Omitirla al editar conserva la guardada.
    api_key: str | None = None
    enabled: bool = True
    default_model: str | None = None
    input_usd_per_mtok: float | None = None
    output_usd_per_mtok: float | None = None


@api.get("/providers")
def providers_list(registry: ProvidersDep) -> dict:
    """Tipos de proveedor disponibles (con sus avisos) y los que configuró el usuario."""
    return {
        "presets": [p.to_dict() for p in PRESETS.values()],
        "providers": [p.to_dict(registry.has_key(p.id)) for p in registry.list()],
    }


@api.put("/providers/{provider_id}")
def provider_put(provider_id: str, req: ProviderBody, registry: ProvidersDep) -> dict:
    """Crea o actualiza un proveedor. La clave va al llavero del sistema."""
    try:
        kind = ProviderKind(req.kind)
    except ValueError as exc:
        known = ", ".join(k.value for k in ProviderKind)
        raise HTTPException(status_code=400,
                            detail=f"Tipo de proveedor desconocido: {req.kind!r}. "
                                   f"Opciones: {known}") from exc
    preset = PRESETS[kind]
    existing = registry.get(provider_id)
    provider = Provider(
        id=provider_id,
        kind=kind,
        name=req.name or (existing.name if existing else preset.label),
        base_url=req.base_url or (existing.base_url if existing else preset.base_url),
        enabled=req.enabled,
        default_model=req.default_model,
        input_usd_per_mtok=req.input_usd_per_mtok,
        output_usd_per_mtok=req.output_usd_per_mtok,
    )
    try:
        saved = registry.save(provider, req.api_key)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_chat_service.cache_clear()
    return saved.to_dict(registry.has_key(provider_id))


@api.delete("/providers/{provider_id}")
def provider_delete(provider_id: str, registry: ProvidersDep) -> dict:
    if not registry.delete(provider_id):
        raise HTTPException(status_code=404, detail=f"No existe el proveedor '{provider_id}'.")
    get_chat_service.cache_clear()
    return {"deleted": provider_id}


@api.get("/providers/{provider_id}/models")
def provider_models(provider_id: str, registry: ProvidersDep) -> dict:
    """Modelos que ofrece el proveedor (consulta su /v1/models)."""
    try:
        client, _ = registry.client(provider_id)
        return {"models": client.list_models()}
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class RedeemRequest(BaseModel):
    code: str


def _cloud_client(registry: ProviderRegistry, provider_id: str):
    try:
        client, provider = registry.client(provider_id)
    except ProviderError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if provider.kind is not ProviderKind.MAGNUS_CLOUD:
        raise HTTPException(status_code=400,
                            detail="Solo Magnus Cloud tiene saldo, paquetes y vales.")
    return client


@api.get("/providers/{provider_id}/account")
def provider_account(provider_id: str, registry: ProvidersDep) -> dict:
    """Saldo de créditos y movimientos en Magnus Cloud."""
    client = _cloud_client(registry, provider_id)
    try:
        return client.account()
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@api.get("/providers/{provider_id}/packs")
def provider_packs(provider_id: str, registry: ProvidersDep) -> dict:
    """Paquetes de créditos que vende Magnus Cloud."""
    client = _cloud_client(registry, provider_id)
    try:
        return client.packs()
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@api.post("/providers/{provider_id}/redeem")
def provider_redeem(provider_id: str, req: RedeemRequest, registry: ProvidersDep) -> dict:
    """Canjea un vale de créditos."""
    client = _cloud_client(registry, provider_id)
    try:
        return client.redeem(req.code)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.post("/providers/{provider_id}/test")
def provider_test(provider_id: str, registry: ProvidersDep) -> dict:
    """Prueba la conexión y la clave sin gastar tokens: solo lista modelos."""
    try:
        client, provider = registry.client(provider_id)
        models = client.list_models()
    except ProviderError as exc:
        return {"ok": False, "detail": str(exc)}
    return {"ok": True, "location": provider.location, "models": len(models),
            "sample": models[:8]}


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
    for cached in (get_settings, get_runtime_manager, get_rag_store, get_chat_service,
                   get_agent_runner):
        cached.cache_clear()
    return updated.to_dict()
