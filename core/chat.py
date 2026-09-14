"""Chat con streaming de tokens, skills, documentos del usuario y medición de cada turno.

`ChatService.stream()` es un generador de eventos que la CLI imprime y el
daemon reenvía por WebSocket:

    {"type": "start", "conversation_id", "model", "skills", "sources",
     "provider", "location"}
    {"type": "thinking", "content"}                    (modelos que razonan)
    {"type": "token", "content"}                       (muchos)
    {"type": "done",  "conversation_id", "message_id", "content", "metrics"}

Antes de generar se resuelven las skills del mensaje (`/nombre` o disparadores)
y, si se pidió, se buscan fragmentos de una colección y hechos de la memoria;
todo eso se suma al system prompt. Mientras el modelo genera, un `PowerMeter`
muestrea la potencia del equipo; al cerrar, el turno se mide con los tokens que
reporta el runtime y se guarda junto a la respuesta.

Por omisión el turno corre en este equipo (Ollama). Con `provider` corre en un
proveedor configurado (vLLM en la red, NVIDIA API con la clave del usuario,
Magnus Cloud): ver `core/providers.py`. Nunca se elige solo.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from core.config import Settings
from core.metering import (
    REFERENCE_HARDWARE_USD,
    PowerMeter,
    amortization_usd_per_hour,
    meter_turn,
    parse_param_size,
    pick_reference,
)
from core.platform import PlatformProfile
from core.rag import RagError, RagStore, format_context
from core.runtime_manager import RuntimeManagerError
from core.skills import SkillRegistry, compose_system_prompt
from core.store import Store, title_from

# Similitud mínima para traer un hecho de la memoria: por debajo, lo que se
# inyecta es ruido que el modelo pequeño tiende a mencionar sin venir al caso.
_MEMORY_MIN_SCORE = 0.35

LOCAL_PROVIDER = "local"


@dataclass
class ChatError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _request_body(model: str, messages: list[dict], stream: bool, options: dict | None,
                  think: bool | None, tools: list[dict] | None = None) -> dict:
    body: dict = {"model": model, "messages": messages, "stream": stream}
    if tools:
        body["tools"] = tools
    if options:
        body["options"] = options
    if think is not None:
        # Poner "/no_think" en el mensaje no basta: medido en el Jetson,
        # qwen3:0.6b razonó 1344 tokens igual. El parámetro de la API sí manda.
        body["think"] = think
    return body


class OllamaChatClient:
    """Cliente de /api/chat de Ollama: streaming para el chat, un paso para agentes."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def stream_chat(self, model: str, messages: list[dict], options: dict | None = None,
                    think: bool | None = None) -> Iterator[dict]:
        body = _request_body(model, messages, True, options, think)
        # Sin límite de lectura corto: en un Jetson la primera carga del modelo
        # tarda decenas de segundos antes del primer token.
        timeout = httpx.Timeout(10.0, read=600.0)
        try:
            with httpx.stream("POST", f"{self.base_url}/api/chat", json=body,
                              timeout=timeout) as response:
                if response.status_code >= 400:
                    response.read()
                    raise ChatError(_ollama_error(response))
                for line in response.iter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise ChatError(f"Ollama: {chunk['error']}")
                    yield chunk
        except httpx.ConnectError as exc:
            raise ChatError(
                f"No se puede conectar con Ollama en {self.base_url}. ¿Está arrancado?"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise ChatError("Ollama dejó de responder a mitad de la respuesta.") from exc

    def chat_once(self, model: str, messages: list[dict], tools: list[dict] | None = None,
                  options: dict | None = None, think: bool | None = None) -> dict:
        """Un paso sin streaming, con herramientas: lo usa el runtime de agentes."""
        body = _request_body(model, messages, False, options, think, tools)
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=body,
                           timeout=httpx.Timeout(10.0, read=600.0))
        except httpx.ConnectError as exc:
            raise ChatError(
                f"No se puede conectar con Ollama en {self.base_url}. ¿Está arrancado?"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise ChatError("Ollama tardó demasiado en responder.") from exc
        if r.status_code >= 400:
            if "does not support tools" in r.text:
                raise ChatError(f"El modelo {model} no soporta herramientas. Elige uno con "
                                "'tools' en el catálogo (magnus catalog --capacidad tools).")
            if "does not support thinking" in r.text:
                raise ChatError(f"El modelo {model} no razona: quita la opción 'think'.")
            raise ChatError(_ollama_error(r))
        return r.json()

    def parameter_size_b(self, model: str) -> float | None:
        """Parámetros del modelo (B) según Ollama, para elegir la referencia de nube."""
        try:
            r = httpx.post(f"{self.base_url}/api/show", json={"model": model}, timeout=10)
            r.raise_for_status()
        except httpx.HTTPError:
            return None
        return parse_param_size(r.json().get("details", {}).get("parameter_size"))


def _ollama_error(response: httpx.Response) -> str:
    try:
        detail = response.json().get("error", response.text)
    except ValueError:
        detail = response.text
    if response.status_code == 404:
        return f"El modelo no está descargado en Ollama: {detail}"
    if "does not support thinking" in str(detail):
        return "Este modelo no razona: quita la opción 'think'."
    return f"Ollama respondió {response.status_code}: {detail}"


class ChatService:
    def __init__(
        self,
        store: Store,
        settings: Settings,
        platform: PlatformProfile,
        client: OllamaChatClient,
        power_sampler: Callable[[], float | None],
        power_interval_s: float = 0.5,
        ensure_loaded: Callable[[str], object] | None = None,
        skills: SkillRegistry | None = None,
        rag: RagStore | None = None,
        remote: Callable[[str], tuple[Any, Any]] | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._client = client
        self._power_sampler = power_sampler
        self._power_interval = power_interval_s
        self._ensure_loaded = ensure_loaded
        self._skills = skills
        self._rag = rag
        # id de proveedor → (cliente con stream_chat, Provider). Ver core/providers.py.
        self._remote = remote
        # Buscar en la memoria calcula un embedding con otro modelo. Donde solo
        # cabe un modelo a la vez (Jetson, laptops de 4–8 GB) eso expulsaría al
        # de chat en cada turno; ahí la memoria se usa solo si se pide.
        self._memory_by_default = platform.max_loaded_models > 1
        self._params_cache: dict[tuple[str, str], float | None] = {}
        hardware_cost = settings.hardware_cost_usd
        if hardware_cost is None:
            hardware_cost = (REFERENCE_HARDWARE_USD.get(platform.family.value, 1000.0)
                             * max(platform.gpu_count, 1))
        self._amortization = amortization_usd_per_hour(
            hardware_cost, settings.hardware_lifetime_years, settings.hours_per_day
        )

    def _params(self, provider: str, client: Any, model: str) -> float | None:
        key = (provider, model)
        if key not in self._params_cache:
            self._params_cache[key] = client.parameter_size_b(model)
        return self._params_cache[key]

    def _retrieve(self, prompt: str, collection: str | None,
                  use_memory: bool | None, k: int) -> tuple[str | None, list[dict]]:
        """Contexto de documentos y memoria para el system prompt, y sus fuentes."""
        if self._rag is None:
            if collection:
                raise ChatError("El RAG no está disponible en este servicio.")
            return None, []
        memory = self._memory_by_default if use_memory is None else use_memory
        try:
            hits = self._rag.search(collection, prompt, k=k) if collection else []
            memories = (self._rag.search_memories(prompt, k=3, min_score=_MEMORY_MIN_SCORE)
                        if memory else [])
        except RagError as exc:
            raise ChatError(str(exc)) from exc
        sources = [{"n": i, "title": h.title, "source": h.source, "score": round(h.score, 4)}
                   for i, h in enumerate(hits, 1)]
        return format_context(hits, memories), sources

    def stream(
        self,
        *,
        model: str,
        message: str,
        conversation_id: str | None = None,
        system: str | None = None,
        options: dict | None = None,
        collection: str | None = None,
        use_memory: bool | None = None,
        rag_k: int = 4,
        think: bool | None = None,
        provider: str | None = None,
    ) -> Iterator[dict]:
        # Todo lo que puede fallar va antes de escribir en la base: un turno que
        # no llega al modelo no deja conversaciones vacías ni mensajes huérfanos.
        if not message.strip():
            raise ChatError("El mensaje está vacío.")
        conv = None
        if conversation_id:
            conv = self._store.get_conversation(conversation_id)
            if conv is None:
                raise ChatError(f"Conversación no encontrada: {conversation_id}")

        provider_id = provider or LOCAL_PROVIDER
        remote = provider_id != LOCAL_PROVIDER
        client: Any = self._client
        remote_provider: Any = None
        if remote:
            if self._remote is None:
                raise ChatError("Este servicio no tiene proveedores externos configurados.")
            client, remote_provider = self._remote(provider_id)
        location = remote_provider.location if remote_provider else LOCAL_PROVIDER

        active = self._skills.resolve(message) if self._skills else []
        # Al modelo le llega el mensaje sin el "/nombre"; en la conversación se
        # guarda tal como lo escribió el usuario.
        prompt = self._skills.strip_invocation(message) if self._skills else message
        # Los embeddings van antes de cargar el modelo de chat: si solo cabe un
        # modelo, calcularlos lo expulsa y así se recarga con la guarda.
        context, sources = self._retrieve(prompt, collection, use_memory, rag_k)
        # Un proveedor remoto no ocupa memoria de este equipo: no hay nada que cargar.
        if self._ensure_loaded and not remote:
            try:
                self._ensure_loaded(model)
            except RuntimeManagerError as exc:
                raise ChatError(str(exc)) from exc

        if conv is None:
            conv = self._store.create_conversation(model=model, title=title_from(message))
        effective_system = compose_system_prompt(system, active)
        if context:
            effective_system = f"{effective_system}\n\n{context}" if effective_system else context

        history = [{"role": m.role, "content": m.content}
                   for m in self._store.messages(conv.id)]
        if effective_system:
            history.insert(0, {"role": "system", "content": effective_system})
        history.append({"role": "user", "content": prompt})
        self._store.add_message(conv.id, "user", message)

        yield {"type": "start", "conversation_id": conv.id, "model": model,
               "skills": [s.name for s in active], "sources": sources,
               "provider": provider_id, "location": location}

        parts: list[str] = []
        final: dict = {}
        ttft: float | None = None
        start = time.monotonic()
        # Generar en otro equipo no consume la GPU de este: no se atribuye energía.
        sampler = (lambda: None) if remote else self._power_sampler
        with PowerMeter(sampler, self._power_interval) as meter:
            for chunk in client.stream_chat(model, history, options, think=think):
                # Modelos que razonan (qwen3, deepseek-r1, gpt-oss): Ollama manda el
                # razonamiento aparte. No es respuesta ni cuenta para el primer
                # token, pero el cliente puede mostrarlo mientras espera.
                thinking = chunk.get("message", {}).get("thinking", "")
                if thinking:
                    yield {"type": "thinking", "content": thinking}
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    if ttft is None:
                        ttft = time.monotonic() - start
                    parts.append(piece)
                    yield {"type": "token", "content": piece}
                if chunk.get("done"):
                    final = chunk
        duration = time.monotonic() - start

        content = "".join(parts)
        eval_ns = final.get("eval_duration") or 0
        # Lo que cuenta el tokenizer del modelo, según el runtime.
        tokens_in = final.get("prompt_eval_count") or 0
        tokens_out = final.get("eval_count") or 0
        metrics = meter_turn(
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_s=duration,
            generation_s=eval_ns / 1e9 if eval_ns else None,
            ttft_s=ttft,
            energy_wh=meter.energy_wh,
            avg_power_w=meter.avg_power_w,
            reference=pick_reference(self._params(provider_id, client, model),
                                     self._settings.cloud_reference),
            electricity_usd_per_kwh=self._settings.electricity_usd_per_kwh,
            amortization_per_hour_usd=self._amortization,
            provider=provider_id,
            location=location,
            provider_cost_usd=(remote_provider.cost_usd(tokens_in, tokens_out)
                               if remote_provider else None),
        )
        saved = self._store.add_message(conv.id, "assistant", content, metrics.to_dict())
        yield {
            "type": "done",
            "conversation_id": conv.id,
            "message_id": saved.id,
            "content": content,
            "metrics": metrics.to_dict(),
        }
