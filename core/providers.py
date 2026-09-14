"""Proveedores de inferencia fuera de Ollama: vLLM en cualquier equipo y APIs con tu clave.

Magnus corre modelos en el equipo del usuario. Cuando la memoria no alcanza,
hay tres salidas y las tres hablan el mismo idioma (la API de OpenAI):

- **vLLM** en otro equipo de la red o en un servidor propio: un DGX Spark, una
  PC con RTX, un B200. Con batching continuo sirve a varias personas a la vez,
  cosa que Ollama no hace bien.
- **APIs con la clave del usuario**: NVIDIA (build.nvidia.com), Groq, OpenRouter
  o cualquier servidor compatible. La cuenta y sus términos son del usuario:
  Magnus solo enruta. Los términos de prueba de NVIDIA prohíben compartir el
  servicio con terceros (§4.2) — por eso nunca hay una clave de Magnus detrás.
- **Magnus Cloud**: el gateway con saldo de créditos (`cloud/`), que corre vLLM
  en hardware propio y cobra por tokens.

Nada de esto se activa solo: el usuario elige proveedor por conversación.

`OpenAICompatClient` devuelve los fragmentos con la MISMA forma que el cliente
de Ollama (`message.content`, `message.thinking`, `done`, `prompt_eval_count`,
`eval_count`), así `ChatService` mide y guarda igual sin importar dónde corrió.
"""

from __future__ import annotations

import enum
import ipaddress
import json
import re
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from urllib.parse import urlparse

import httpx

from core.chat import ChatError
from core.secrets import SecretStore

_FILE = "providers.json"
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class ProviderKind(str, enum.Enum):
    VLLM = "vllm"
    NVIDIA = "nvidia"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    OPENAI_COMPATIBLE = "openai-compatible"
    MAGNUS_CLOUD = "magnus-cloud"


@dataclass(frozen=True)
class ProviderPreset:
    kind: ProviderKind
    label: str
    base_url: str
    needs_key: bool
    # Dónde se consigue la clave, para enlazarlo desde la app.
    key_url: str | None
    # Aviso que la app muestra al conectar. Vacío si no hace falta.
    notice: str
    description: str

    def to_dict(self) -> dict:
        return asdict(self) | {"kind": self.kind.value}


PRESETS: dict[ProviderKind, ProviderPreset] = {
    p.kind: p
    for p in (
        ProviderPreset(
            ProviderKind.VLLM, "vLLM en tu red", "http://127.0.0.1:8000/v1", False, None,
            "",
            "Un servidor vLLM en otro equipo tuyo: DGX Spark, PC con RTX o servidor. "
            "Sirve a varias personas a la vez.",
        ),
        ProviderPreset(
            ProviderKind.NVIDIA, "NVIDIA API", "https://integrate.api.nvidia.com/v1", True,
            "https://build.nvidia.com",
            "La prueba gratuita de NVIDIA es para evaluar, no para producción, y NVIDIA "
            "puede usar lo que envíes para mejorar sus modelos. No envíes datos personales "
            "ni confidenciales.",
            "Más de 100 modelos alojados por NVIDIA con tu propia clave.",
        ),
        ProviderPreset(
            ProviderKind.GROQ, "Groq", "https://api.groq.com/openai/v1", True,
            "https://console.groq.com/keys",
            "Tus mensajes salen de tu equipo hacia Groq.",
            "Inferencia muy rápida con capa gratuita limitada.",
        ),
        ProviderPreset(
            ProviderKind.OPENROUTER, "OpenRouter", "https://openrouter.ai/api/v1", True,
            "https://openrouter.ai/keys",
            "Tus mensajes salen de tu equipo hacia OpenRouter y el proveedor que elija.",
            "Cientos de modelos de varios proveedores con una sola clave.",
        ),
        ProviderPreset(
            ProviderKind.OPENAI_COMPATIBLE, "Servidor compatible", "http://127.0.0.1:8000/v1",
            False, None, "",
            "Cualquier servidor con la API de OpenAI: LM Studio, llama.cpp, TensorRT-LLM.",
        ),
        ProviderPreset(
            ProviderKind.MAGNUS_CLOUD, "Magnus Cloud", "https://cloud.magnus.local/v1", True,
            None,
            "Tus mensajes salen de tu equipo hacia Magnus Cloud. No se guardan ni se usan "
            "para entrenar.",
            "Modelos abiertos en hardware NVIDIA propio, pagados con créditos.",
        ),
    )
}


# Redes donde vive un equipo del usuario. Explícitas: `ipaddress.is_private`
# también da True para rangos de documentación como 203.0.113.0/24.
_LAN_NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",   # RFC 1918
    "127.0.0.0/8", "169.254.0.0/16",                   # loopback, link-local
    "100.64.0.0/10",                                   # CGNAT: Tailscale
    "::1/128", "fc00::/7", "fe80::/10",
))


def _is_private(base_url: str) -> bool:
    host = urlparse(base_url).hostname or ""
    if host in ("localhost",) or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in net for net in _LAN_NETWORKS if ip.version == net.version)


@dataclass(frozen=True)
class Provider:
    id: str
    kind: ProviderKind
    name: str
    base_url: str
    enabled: bool = True
    default_model: str | None = None
    # Precio real que cobra el proveedor (USD por millón). None: desconocido.
    input_usd_per_mtok: float | None = None
    output_usd_per_mtok: float | None = None

    @property
    def location(self) -> str:
        """'lan' si el servidor está en la red del usuario, 'cloud' si sale de ella."""
        if self.kind in (ProviderKind.VLLM, ProviderKind.OPENAI_COMPATIBLE):
            return "lan" if _is_private(self.base_url) else "cloud"
        return "cloud"

    @property
    def preset(self) -> ProviderPreset:
        return PRESETS[self.kind]

    def cost_usd(self, tokens_in: int, tokens_out: int) -> float | None:
        if self.input_usd_per_mtok is None or self.output_usd_per_mtok is None:
            return None
        return (tokens_in * self.input_usd_per_mtok + tokens_out * self.output_usd_per_mtok) / 1e6

    def to_dict(self, has_key: bool = False) -> dict:
        return asdict(self) | {
            "kind": self.kind.value,
            "location": self.location,
            "has_key": has_key,
            "needs_key": self.preset.needs_key,
            "notice": self.preset.notice,
        }


@dataclass
class ProviderError(ChatError):
    """Error de un proveedor remoto. Hereda de ChatError: el chat ya sabe mostrarlo."""


class ProviderRegistry:
    """Proveedores configurados, en `providers.json`; sus claves, en `SecretStore`."""

    def __init__(self, directory: Path, secrets: SecretStore) -> None:
        self._path = Path(directory) / _FILE
        self._secrets = secrets

    def _read(self) -> list[dict]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8")).get("providers", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            return []

    def _write(self, providers: list[Provider]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"providers": [asdict(p) | {"kind": p.kind.value} for p in providers]}
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def list(self) -> list[Provider]:
        result = []
        for raw in self._read():
            try:
                result.append(Provider(**(raw | {"kind": ProviderKind(raw["kind"])})))
            except (KeyError, TypeError, ValueError):
                continue  # entrada corrupta o de una versión futura: se ignora
        return result

    def get(self, provider_id: str) -> Provider | None:
        return next((p for p in self.list() if p.id == provider_id), None)

    def has_key(self, provider_id: str) -> bool:
        return bool(self._secrets.get(_key_name(provider_id)))

    def save(self, provider: Provider, api_key: str | None = None) -> Provider:
        if not _ID.match(provider.id):
            raise ProviderError("El identificador del proveedor solo admite minúsculas, "
                                "números y guiones (máx. 40).")
        if provider.id == "local":
            raise ProviderError("'local' está reservado para los modelos de este equipo.")
        parsed = urlparse(provider.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ProviderError(f"URL no válida: {provider.base_url!r}. "
                                "Ejemplo: http://192.168.1.20:8000/v1")
        if parsed.scheme == "http" and not _is_private(provider.base_url):
            raise ProviderError("Un servidor fuera de tu red debe usar https: la clave y los "
                                "mensajes viajarían sin cifrar.")
        provider = replace(provider, base_url=provider.base_url.rstrip("/"))
        if api_key:
            self._secrets.set(_key_name(provider.id), api_key.strip())
        elif provider.preset.needs_key and not self.has_key(provider.id):
            raise ProviderError(f"{provider.preset.label} necesita una clave de API.")
        others = [p for p in self.list() if p.id != provider.id]
        self._write([*others, provider])
        return provider

    def delete(self, provider_id: str) -> bool:
        providers = self.list()
        kept = [p for p in providers if p.id != provider_id]
        if len(kept) == len(providers):
            return False
        self._write(kept)
        self._secrets.delete(_key_name(provider_id))
        return True

    def client(self, provider_id: str) -> tuple[OpenAICompatClient, Provider]:
        provider = self.get(provider_id)
        if provider is None:
            raise ProviderError(f"No hay un proveedor configurado con id '{provider_id}'.")
        if not provider.enabled:
            raise ProviderError(f"El proveedor '{provider.name}' está desactivado.")
        key = self._secrets.get(_key_name(provider_id))
        return OpenAICompatClient(provider.base_url, key, provider.name), provider


def _key_name(provider_id: str) -> str:
    return f"provider:{provider_id}"


class OpenAICompatClient:
    """Cliente de `/v1/chat/completions` y `/v1/models` con forma de fragmento de Ollama."""

    def __init__(self, base_url: str, api_key: str | None, name: str = "el proveedor",
                 transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._name = name
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(headers=headers, transport=transport,
                                  timeout=httpx.Timeout(10.0, read=600.0))

    def _error(self, response: httpx.Response, model: str | None = None) -> ProviderError:
        try:
            body = response.json()
            detail = body.get("error", body)
            if isinstance(detail, dict):
                detail = detail.get("message") or json.dumps(detail, ensure_ascii=False)
        except ValueError:
            detail = response.text
        status = response.status_code
        if status == 401 or status == 403:
            return ProviderError(f"La clave de {self._name} no es válida o no tiene permiso.")
        if status == 402:
            return ProviderError(f"Saldo insuficiente en {self._name}. Recarga créditos para "
                                 "seguir.")
        if status == 429:
            return ProviderError(f"{self._name} limitó las peticiones (cuota o velocidad). "
                                 "Espera un momento o usa un modelo local.")
        if status == 404 and model:
            return ProviderError(f"El modelo '{model}' no existe en {self._name}.")
        return ProviderError(f"{self._name} respondió {status}: {detail}")

    def _connect_error(self, exc: Exception) -> ProviderError:
        return ProviderError(f"No se puede conectar con {self._name} en {self.base_url}. "
                             "Revisa la URL y que el servidor esté encendido.")

    def list_models(self) -> list[str]:
        try:
            r = self._http.get(f"{self.base_url}/models", timeout=15)
        except httpx.HTTPError as exc:
            raise self._connect_error(exc) from exc
        if r.status_code >= 400:
            raise self._error(r)
        return sorted(m.get("id", "") for m in r.json().get("data", []) if m.get("id"))

    def parameter_size_b(self, model: str) -> float | None:
        """Tamaño del modelo desde su nombre ('llama-3.1-70b-instruct' → 70)."""
        match = re.search(r"(\d+(?:\.\d+)?)b\b", model.lower())
        return float(match.group(1)) if match else None

    def stream_chat(self, model: str, messages: list[dict], options: dict | None = None,
                    think: bool | None = None) -> Iterator[dict]:
        body: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            # Sin esto la API de OpenAI no manda el conteo de tokens en streaming.
            "stream_options": {"include_usage": True},
        }
        options = options or {}
        for src, dst in (("temperature", "temperature"), ("top_p", "top_p"),
                         ("num_predict", "max_tokens"), ("seed", "seed")):
            if src in options:
                body[dst] = options[src]
        if think is not None:
            # vLLM con Qwen3 / DeepSeek: el razonamiento se apaga en la plantilla.
            body["chat_template_kwargs"] = {"enable_thinking": think}

        usage: dict = {}
        started = time.monotonic()
        first_token: float | None = None
        try:
            with self._http.stream("POST", f"{self.base_url}/chat/completions",
                                   json=body) as response:
                if response.status_code >= 400:
                    response.read()
                    raise self._error(response, model)
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    for choice in chunk.get("choices", []):
                        delta = choice.get("delta", {})
                        thinking = delta.get("reasoning_content") or delta.get("reasoning") or ""
                        content = delta.get("content") or ""
                        if content and first_token is None:
                            first_token = time.monotonic()
                        if thinking or content:
                            yield {"message": {"content": content, "thinking": thinking},
                                   "done": False}
        except httpx.ConnectError as exc:
            raise self._connect_error(exc) from exc
        except httpx.ReadTimeout as exc:
            raise ProviderError(f"{self._name} dejó de responder a mitad de la respuesta.") \
                from exc

        ended = time.monotonic()
        generation_ns = int((ended - (first_token or started)) * 1e9)
        yield {
            "message": {"content": ""},
            "done": True,
            "prompt_eval_count": usage.get("prompt_tokens", 0),
            "eval_count": usage.get("completion_tokens", 0),
            "eval_duration": generation_ns,
        }
