"""Chat con streaming de tokens y medición de cada turno.

`ChatService.stream()` es un generador de eventos que la CLI imprime y el
daemon reenvía por WebSocket:

    {"type": "start", "conversation_id", "model"}
    {"type": "token", "content"}                       (muchos)
    {"type": "done",  "conversation_id", "message_id", "content", "metrics"}

Mientras el modelo genera, un `PowerMeter` muestrea la potencia del equipo;
al cerrar, el turno se mide con los tokens que reporta el runtime y se guarda
junto a la respuesta.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

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
from core.runtime_manager import RuntimeManagerError
from core.store import Store, title_from


@dataclass
class ChatError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


class OllamaChatClient:
    """Streaming de /api/chat de Ollama (una línea JSON por fragmento)."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def stream_chat(self, model: str, messages: list[dict],
                    options: dict | None = None) -> Iterator[dict]:
        body: dict = {"model": model, "messages": messages, "stream": True}
        if options:
            body["options"] = options
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
    ) -> None:
        self._ensure_loaded = ensure_loaded
        self._store = store
        self._settings = settings
        self._client = client
        self._power_sampler = power_sampler
        self._power_interval = power_interval_s
        self._params_cache: dict[str, float | None] = {}
        hardware_cost = settings.hardware_cost_usd
        if hardware_cost is None:
            hardware_cost = (REFERENCE_HARDWARE_USD.get(platform.family.value, 1000.0)
                             * max(platform.gpu_count, 1))
        self._amortization = amortization_usd_per_hour(
            hardware_cost, settings.hardware_lifetime_years, settings.hours_per_day
        )

    def _params(self, model: str) -> float | None:
        if model not in self._params_cache:
            self._params_cache[model] = self._client.parameter_size_b(model)
        return self._params_cache[model]

    def stream(
        self,
        *,
        model: str,
        message: str,
        conversation_id: str | None = None,
        system: str | None = None,
        options: dict | None = None,
    ) -> Iterator[dict]:
        if not message.strip():
            raise ChatError("El mensaje está vacío.")
        if self._ensure_loaded:
            # Antes de guardar nada: si el modelo no puede cargarse, el turno
            # no deja un mensaje del usuario huérfano en la conversación.
            try:
                self._ensure_loaded(model)
            except RuntimeManagerError as exc:
                raise ChatError(str(exc)) from exc
        if conversation_id:
            conv = self._store.get_conversation(conversation_id)
            if conv is None:
                raise ChatError(f"Conversación no encontrada: {conversation_id}")
        else:
            conv = self._store.create_conversation(model=model, title=title_from(message))

        history = [{"role": m.role, "content": m.content}
                   for m in self._store.messages(conv.id)]
        if system:
            history.insert(0, {"role": "system", "content": system})
        history.append({"role": "user", "content": message})
        self._store.add_message(conv.id, "user", message)

        yield {"type": "start", "conversation_id": conv.id, "model": model}

        parts: list[str] = []
        final: dict = {}
        ttft: float | None = None
        start = time.monotonic()
        with PowerMeter(self._power_sampler, self._power_interval) as meter:
            for chunk in self._client.stream_chat(model, history, options):
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
        metrics = meter_turn(
            model=model,
            # Lo que cuenta el tokenizer del modelo, según el runtime.
            tokens_in=final.get("prompt_eval_count") or 0,
            tokens_out=final.get("eval_count") or 0,
            duration_s=duration,
            generation_s=eval_ns / 1e9 if eval_ns else None,
            ttft_s=ttft,
            energy_wh=meter.energy_wh,
            avg_power_w=meter.avg_power_w,
            reference=pick_reference(self._params(model), self._settings.cloud_reference),
            electricity_usd_per_kwh=self._settings.electricity_usd_per_kwh,
            amortization_per_hour_usd=self._amortization,
        )
        saved = self._store.add_message(conv.id, "assistant", content, metrics.to_dict())
        yield {
            "type": "done",
            "conversation_id": conv.id,
            "message_id": saved.id,
            "content": content,
            "metrics": metrics.to_dict(),
        }
