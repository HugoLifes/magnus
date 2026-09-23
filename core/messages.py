"""Proxy de la API de mensajes de Anthropic sobre los modelos de este equipo.

Claude Code, Codex CLI, OpenCode y Aider hablan el protocolo de Anthropic
(`POST /v1/messages`). Ollama también lo habla desde su versión 0.14, así que
Magnus **no reimplementa el formato**: se pone en medio y aporta lo que Ollama no
tiene, que es justo lo que hace a Magnus distinto de apuntar el cliente a Ollama:

- **elige el modelo**: el cliente pide `claude-sonnet-4-5`, que aquí no existe;
  Magnus lo traduce al mejor modelo de código descargado en este equipo;
- **guarda de memoria**: carga el modelo con `RuntimeManager`, que en memoria
  unificada libera caché y comprueba que quepa antes de intentarlo;
- **medidor**: cada turno queda registrado con tokens, energía y ahorro frente a
  la nube, así que programar con Claude Code suma al contador de ahorro;
- **token de acceso** del daemon, que Ollama no tiene.

Todo lo que el cliente manda se reenvía tal cual salvo el modelo, y todo lo que
el runtime responde vuelve intacto: si el protocolo cambia, Magnus no estorba.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from core.catalog import CODE, TOOLS, get_catalog_model
from core.config import Settings
from core.metering import (
    REFERENCE_HARDWARE_USD,
    PowerMeter,
    TurnMetrics,
    amortization_usd_per_hour,
    meter_turn,
    parse_param_size,
    pick_reference,
)
from core.platform import PlatformProfile
from core.runtime_manager import RuntimeManager, RuntimeManagerError
from core.store import Store

# Nombres que delatan a un modelo de la nube: el cliente pide uno de estos y hay
# que traducirlo a lo que sí corre aquí.
_REMOTE_HINTS = ("claude", "sonnet", "haiku", "opus", "gpt-", "o1", "o3", "gemini", "grok")

# Pedir explícitamente que Magnus elija. Es lo que manda `magnus claude`, para no
# atar el cliente a un modelo concreto del equipo.
AUTO_MODELS = ("", "magnus-auto", "auto", "magnus")

_TIMEOUT = httpx.Timeout(600.0, connect=5.0, read=None)


class ProxyError(Exception):
    """No se pudo atender la petición. El mensaje va en español, al usuario."""


@dataclass(frozen=True)
class ProxyTurn:
    """Resultado de un turno no-streaming: lo que responde el modelo y su medición."""

    payload: dict
    metrics: TurnMetrics


class MessagesProxy:
    """Traduce, vigila la memoria y mide los turnos de la API de mensajes."""

    def __init__(
        self,
        *,
        manager: RuntimeManager,
        store: Store,
        settings: Settings,
        platform: PlatformProfile,
        ollama_url: str = "http://127.0.0.1:11434",
        power_sampler: Callable[[], float | None] | None = None,
        power_interval_s: float = 0.5,
        post: Callable[..., httpx.Response] | None = None,
        stream_post: Callable[..., Any] | None = None,
    ) -> None:
        self._manager = manager
        self._store = store
        self._settings = settings
        self._platform = platform
        self._url = ollama_url.rstrip("/") + "/v1/messages"
        self._power_sampler = power_sampler or (lambda: None)
        self._power_interval = power_interval_s
        self._post = post or httpx.post
        self._stream_post = stream_post or self._default_stream
        hardware_cost = settings.hardware_cost_usd
        if hardware_cost is None:
            hardware_cost = (REFERENCE_HARDWARE_USD.get(platform.family.value, 1000.0)
                             * max(platform.gpu_count, 1))
        self._amortization = amortization_usd_per_hour(
            hardware_cost, settings.hardware_lifetime_years, settings.hours_per_day
        )

    # ------------------------------------------------------------------
    # Elegir el modelo
    # ------------------------------------------------------------------
    def resolve_model(self, requested: str) -> str:
        """Modelo local que atenderá la petición.

        Si el cliente pide algo que está descargado, se respeta. Si pide un
        modelo de la nube (Claude Code siempre lo hace), se elige el mejor modelo
        de código de este equipo.
        """
        requested = (requested or "").strip()
        local = self._manager.list_available()
        auto = requested.lower() in AUTO_MODELS
        if not local:
            raise ProxyError(
                "No hay ningún modelo descargado en este equipo. Descarga uno para "
                "programar, por ejemplo: magnus fetch qwen2.5-coder:7b"
            )
        if not auto and (requested in local or f"{requested}:latest" in local):
            return requested
        if not auto and not self._looks_remote(requested):
            raise ProxyError(
                f"El modelo {requested!r} no está descargado. Descárgalo con "
                f"`magnus fetch {requested}` o deja que Magnus elija el de este equipo."
            )
        return self._best_code_model(local)

    @staticmethod
    def _looks_remote(model: str) -> bool:
        low = model.lower()
        return any(hint in low for hint in _REMOTE_HINTS)

    @staticmethod
    def _best_code_model(local: list[str]) -> str:
        """El mejor modelo descargado para programar: código, herramientas, tamaño."""
        def score(model_id: str) -> tuple[int, int, float]:
            entry = get_catalog_model(model_id) or get_catalog_model(model_id.split(":")[0])
            caps = entry.capabilities if entry else ()
            params = entry.params_b if entry else (parse_param_size(model_id) or 0.0)
            return (CODE in caps, TOOLS in caps, params)

        return max(local, key=score)

    # ------------------------------------------------------------------
    # Turnos
    # ------------------------------------------------------------------
    def complete(self, request: dict) -> ProxyTurn:
        """Turno sin streaming: devuelve la respuesta de Anthropic y su medición."""
        model, body = self._prepare(request, stream=False)
        start = time.monotonic()
        with PowerMeter(self._power_sampler, self._power_interval) as meter:
            try:
                response = self._post(self._url, json=body, timeout=_TIMEOUT)
            except httpx.HTTPError as exc:
                raise ProxyError(f"No se pudo hablar con el runtime local: {exc}") from exc
        duration = time.monotonic() - start

        if response.status_code >= 400:
            raise ProxyError(_runtime_error(response))
        payload = response.json()
        usage = payload.get("usage") or {}
        metrics = self._meter(
            model=model,
            tokens_in=int(usage.get("input_tokens") or 0),
            tokens_out=int(usage.get("output_tokens") or 0),
            duration=duration,
            ttft=None,
            meter=meter,
        )
        return ProxyTurn(payload=payload, metrics=metrics)

    def stream(self, request: dict) -> Iterator[bytes]:
        """Turno con streaming: reenvía los eventos tal cual y mide al final.

        El cliente recibe exactamente lo que produce el runtime; Magnus solo lee
        de paso los eventos `message_start` y `message_delta`, que es donde viaja
        el conteo de tokens.
        """
        model, body = self._prepare(request, stream=True)
        start = time.monotonic()
        ttft: float | None = None
        tokens_in = tokens_out = 0

        with (PowerMeter(self._power_sampler, self._power_interval) as meter,
              self._stream_post(self._url, body) as lines):
            for line in lines:
                text = line.decode() if isinstance(line, bytes) else line
                if text.startswith("data:"):
                    event = _parse_event(text[5:].strip())
                    kind = event.get("type")
                    if kind == "message_start":
                        usage = (event.get("message") or {}).get("usage") or {}
                        tokens_in = int(usage.get("input_tokens") or tokens_in)
                    elif kind == "content_block_delta" and ttft is None:
                        ttft = time.monotonic() - start
                    elif kind == "message_delta":
                        usage = event.get("usage") or {}
                        tokens_out = int(usage.get("output_tokens") or tokens_out)
                    elif kind == "error":
                        raise ProxyError(_event_error(event))
                yield (text + "\n").encode()

        self._meter(
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration=time.monotonic() - start,
            ttft=ttft,
            meter=meter,
        )

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------
    def _prepare(self, request: dict, *, stream: bool) -> tuple[str, dict]:
        """Elige el modelo, lo carga con guarda de memoria y arma el cuerpo."""
        if not isinstance(request, dict) or not request.get("messages"):
            raise ProxyError("La petición no trae mensajes.")
        model = self.resolve_model(str(request.get("model", "")))
        try:
            self._manager.ensure_loaded(model)
        except RuntimeManagerError as exc:
            raise ProxyError(str(exc)) from exc
        body = dict(request)
        body["model"] = model
        body["stream"] = stream
        return model, body

    def _meter(self, *, model: str, tokens_in: int, tokens_out: int, duration: float,
               ttft: float | None, meter: PowerMeter) -> TurnMetrics:
        entry = get_catalog_model(model)
        params = entry.params_b if entry else parse_param_size(model)
        metrics = meter_turn(
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_s=duration,
            ttft_s=ttft,
            energy_wh=meter.energy_wh,
            avg_power_w=meter.avg_power_w,
            reference=pick_reference(params, self._settings.cloud_reference),
            electricity_usd_per_kwh=self._settings.electricity_usd_per_kwh,
            amortization_per_hour_usd=self._amortization,
        )
        self._store.record_turn("messages", metrics.to_dict())
        return metrics

    def _default_stream(self, url: str, body: dict):
        return _StreamLines(url, body)


class _StreamLines:
    """Context manager que abre el POST en streaming y entrega líneas."""

    def __init__(self, url: str, body: dict) -> None:
        self._url = url
        self._body = body
        self._ctx = None

    def __enter__(self) -> Iterator[str]:
        self._ctx = httpx.stream("POST", self._url, json=self._body, timeout=_TIMEOUT)
        response = self._ctx.__enter__()
        if response.status_code >= 400:
            response.read()
            raise ProxyError(_runtime_error(response))
        return response.iter_lines()

    def __exit__(self, *exc_info) -> None:
        if self._ctx is not None:
            self._ctx.__exit__(*exc_info)


def _parse_event(data: str) -> dict:
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _runtime_error(response: httpx.Response) -> str:
    try:
        detail = response.json().get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        detail = response.text[:300]
    return f"El runtime respondió {response.status_code}: {detail or 'sin detalle'}"


def _event_error(event: dict) -> str:
    detail = (event.get("error") or {}).get("message", "")
    return f"El runtime cortó el turno: {detail or 'sin detalle'}"
