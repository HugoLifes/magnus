"""Gestión del ciclo de vida de modelos en runtimes de inferencia.

Expone una interfaz única — `serve()` / `stop()` / `list_loaded()` / `pull()` —
que hoy arranca y para modelos en Ollama (vía su HTTP API). La misma interfaz
servirá para vLLM sin cambiar el contrato hacia arriba.

Ollama se gestiona así:
  - Descargar → POST /api/pull en streaming: una línea JSON por evento con
               `completed`/`total`, para mostrar progreso. Sin streaming, un
               modelo grande tardaba más que el timeout y la carga fallaba.
  - Cargar   → POST /api/generate con keep_alive=-1 para que Ollama no lo
               expulse. ANTES se comprueba la memoria (`load_memory_verdict`):
               en memoria unificada cargar algo que no cabe cuelga el equipo.
  - Liberar  → POST /api/generate con keep_alive=0 (no borra del disco).
  - Borrar   → DELETE /api/delete.
  - Estado   → GET /api/ps (cargados) y GET /api/tags (en disco).
"""

from __future__ import annotations

import enum
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.compatibility import load_memory_verdict, ollama_required_gib
from core.hardware import GPU, detect_gpus
from core.reclaim import reclaim_for

_BYTES_PER_GIB = 1024**3


class RuntimeBackend(str, enum.Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"


@dataclass
class LoadedModel:
    model_id: str
    backend: RuntimeBackend
    size_vram_gib: float | None
    details: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LocalModel:
    """Modelo descargado en el runtime (en disco, cargado o no)."""
    model_id: str
    size_gib: float | None
    parameter_size: str | None
    quantization: str | None
    family: str | None
    modified_at: str | None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RuntimeManagerError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _is_out_of_memory(exc: RuntimeManagerError) -> bool:
    """Ollama en Jetson: `cudaMalloc failed: out of memory` / `unable to allocate CUDA0 buffer`."""
    text = str(exc).lower()
    return "out of memory" in text or "unable to allocate" in text


def friendly_ollama_error(detail: str) -> str:
    """Traduce los errores de Ollama que el usuario puede resolver.

    Medido en el Jetson: Ollama 0.6.5 (imagen dustynv/ollama:r36.4.0) no puede
    descargar qwen3 — el registro responde 412 "requires a newer version".
    """
    if "newer version of ollama" in detail.lower():
        return ("Este modelo necesita una versión de Ollama más nueva que la instalada. "
                "Actualiza Ollama (en Jetson, una imagen reciente: ver docs/JETSON.md) "
                "o elige otro modelo del catálogo.")
    return f"Ollama: {detail.strip()}"


def _no_ollama(base_url: str) -> str:
    return (f"No se puede conectar con Ollama en {base_url}. "
            "¿Está arrancado? Ejecuta: ollama serve")


class OllamaClient:
    """Cliente HTTP mínimo para la API local de Ollama (por defecto :11434)."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str) -> Any:
        try:
            r = httpx.get(f"{self.base_url}{path}", timeout=10)
            r.raise_for_status()
            return r.json()
        except httpx.ConnectError as exc:
            raise RuntimeManagerError(_no_ollama(self.base_url)) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeManagerError(f"Ollama respondió {exc.response.status_code}: {exc.response.text}") from exc

    def _post(self, path: str, body: dict) -> Any:
        try:
            r = httpx.post(f"{self.base_url}{path}", json=body, timeout=300)
            r.raise_for_status()
            return r.json() if r.content else {}
        except httpx.ConnectError as exc:
            raise RuntimeManagerError(_no_ollama(self.base_url)) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeManagerError(f"Ollama respondió {exc.response.status_code}: {exc.response.text}") from exc

    def _delete(self, path: str, body: dict) -> None:
        try:
            r = httpx.request("DELETE", f"{self.base_url}{path}", json=body, timeout=30)
            r.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeManagerError(_no_ollama(self.base_url)) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeManagerError(f"Ollama respondió {exc.response.status_code}: {exc.response.text}") from exc

    def is_available(self) -> bool:
        try:
            httpx.get(f"{self.base_url}/", timeout=3)
            return True
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def version(self) -> str | None:
        """Versión de Ollama, o None si no responde."""
        try:
            return self._get("/api/version").get("version")
        except RuntimeManagerError:
            return None

    def list_local(self) -> list[dict]:
        """Modelos disponibles localmente (en disco)."""
        data = self._get("/api/tags")
        return data.get("models", [])

    def list_running(self) -> list[dict]:
        """Modelos cargados ahora mismo en VRAM (GET /api/ps)."""
        data = self._get("/api/ps")
        return data.get("models", [])

    def pull_stream(self, model_id: str) -> Iterator[dict]:
        """Descarga con progreso: un evento JSON por línea de /api/pull."""
        # Sin límite de lectura: entre capas Ollama puede tardar en verificar.
        timeout = httpx.Timeout(10.0, read=None)
        try:
            with httpx.stream("POST", f"{self.base_url}/api/pull",
                              json={"name": model_id, "stream": True}, timeout=timeout) as r:
                if r.status_code >= 400:
                    r.read()
                    raise RuntimeManagerError(friendly_ollama_error(r.text))
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if "error" in event:
                        raise RuntimeManagerError(friendly_ollama_error(event["error"]))
                    yield event
        except httpx.ConnectError as exc:
            raise RuntimeManagerError(_no_ollama(self.base_url)) from exc

    def pull(self, model_id: str) -> None:
        """Descarga el modelo si Ollama no lo tiene todavía (sin progreso)."""
        for _ in self.pull_stream(model_id):
            pass

    def _keep_alive(self, model_id: str, keep_alive: int) -> None:
        try:
            self._post("/api/generate",
                       {"model": model_id, "prompt": "", "keep_alive": keep_alive, "stream": False})
        except RuntimeManagerError as exc:
            if "does not support generate" not in str(exc):
                raise
            # Modelos de embeddings (nomic-embed-text, bge-m3): Ollama no los
            # carga con generate — medido con 0.34.0 — pero sí con embed.
            self._post("/api/embed",
                       {"model": model_id, "input": "magnus", "keep_alive": keep_alive})

    def load_into_vram(self, model_id: str) -> None:
        """Carga el modelo en VRAM con keep_alive=-1 (no expulsar)."""
        self._keep_alive(model_id, -1)

    def unload_from_vram(self, model_id: str) -> None:
        """Libera VRAM del modelo sin borrar los pesos del disco."""
        self._keep_alive(model_id, 0)

    def delete(self, model_id: str) -> None:
        """Elimina el modelo del disco local de Ollama."""
        self._delete("/api/delete", {"name": model_id})


class RuntimeManager:
    """Gestiona el ciclo de vida de modelos sobre uno o varios backends.

    Hoy solo usa Ollama. La misma interfaz pública (`serve`, `stop`,
    `list_loaded`, `list_available`, `pull`) será implementada para vLLM.
    """

    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        gpu_provider: Callable[[], list[GPU]] = detect_gpus,
        reclaimer: Callable[[float], float | None] | None = reclaim_for,
    ) -> None:
        self._ollama = OllamaClient(ollama_url)
        self._gpus = gpu_provider
        self._reclaimer = reclaimer

    def ensure_loaded(self, model_id: str) -> LoadedModel | None:
        """Garantiza que el modelo esté cargado antes de usarlo.

        Ollama expulsa los modelos tras un rato sin uso y los recarga solo en la
        siguiente petición — sin guarda de memoria ni liberación de caché, que
        es justo la carga que falla en un Jetson. Aquí se recarga por `serve()`.
        Devuelve None si ya estaba cargado.
        """
        self._require(RuntimeBackend.OLLAMA)
        for m in self._ollama.list_running():
            if m.get("name") in (model_id, f"{model_id}:latest"):
                return None
        if not self._model_exists_locally(model_id):
            raise RuntimeManagerError(
                f"El modelo {model_id!r} no está descargado. Descárgalo con: magnus fetch {model_id}"
            )
        return self.serve(model_id, pull_if_missing=False)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def serve(
        self,
        model_id: str,
        backend: RuntimeBackend = RuntimeBackend.OLLAMA,
        pull_if_missing: bool = True,
        force: bool = False,
    ) -> LoadedModel:
        """Carga `model_id` en VRAM usando `backend`.

        Si `pull_if_missing=True` y Ollama no tiene el modelo localmente,
        lo descarga primero (puede tardar según el tamaño).

        Antes de cargar comprueba que quepa: en memoria unificada se niega si
        no hay memoria libre (salvo `force=True`); en GPU dedicada solo avisa.

        Returns el `LoadedModel` con el estado tras la carga.
        Raises `RuntimeManagerError` si algo va mal.
        """
        self._require(backend)

        if pull_if_missing and not self._model_exists_locally(model_id):
            self._ollama.pull(model_id)

        gpus = self._gpus()
        gpu = gpus[0] if gpus else None
        size = self._local_size_gib(model_id)
        allowed, note = load_memory_verdict(size, gpu)
        if not allowed and not force:
            raise RuntimeManagerError(note or "No hay memoria suficiente para cargar el modelo.")
        unified = bool(gpu and gpu.unified_memory and self._reclaimer)
        if unified and size:
            # MemAvailable dice que cabe; hay que convertir la caché en memoria
            # libre de verdad antes de que CUDA la pida (ver core/reclaim.py).
            self._reclaimer(ollama_required_gib(size))

        try:
            self._ollama.load_into_vram(model_id)
        except RuntimeManagerError as exc:
            if not (unified and _is_out_of_memory(exc)):
                raise
            # Segundo y último intento: desalojar toda la caché recuperable.
            self._reclaimer(float("inf"))
            try:
                self._ollama.load_into_vram(model_id)
            except RuntimeManagerError as retry_exc:
                if not _is_out_of_memory(retry_exc):
                    raise
                raise RuntimeManagerError(
                    "La GPU no pudo reservar memoria aunque se liberó la caché: la memoria "
                    "compartida la ocupan otros procesos. Cierra aplicaciones (navegador, "
                    "escritorio gráfico) o elige un modelo más pequeño (magnus catalog)."
                ) from retry_exc
        loaded = self._build_loaded_model(model_id, backend)
        if note:
            loaded.notes.append(note)
        return loaded

    def stop(
        self,
        model_id: str,
        backend: RuntimeBackend = RuntimeBackend.OLLAMA,
        delete_local: bool = False,
    ) -> None:
        """Libera el modelo de VRAM.

        Con `delete_local=True` también borra los pesos del disco de Ollama.
        """
        self._require(backend)
        self._ollama.unload_from_vram(model_id)
        if delete_local:
            self._ollama.delete(model_id)

    def pull(self, model_id: str) -> Iterator[dict]:
        """Descarga con progreso normalizado: status, completed, total, percent."""
        self._require(RuntimeBackend.OLLAMA)
        for event in self._ollama.pull_stream(model_id):
            total = event.get("total")
            completed = event.get("completed")
            percent = round(completed / total * 100, 1) if total and completed is not None else None
            yield {
                "status": event.get("status", ""),
                "digest": event.get("digest"),
                "completed": completed,
                "total": total,
                "percent": percent,
            }

    def delete(self, model_id: str) -> None:
        """Borra el modelo del disco (lo libera de VRAM si estaba cargado)."""
        self._require(RuntimeBackend.OLLAMA)
        self._ollama.delete(model_id)

    def list_loaded(self) -> list[LoadedModel]:
        """Modelos cargados ahora mismo en VRAM (todos los backends)."""
        if not self._ollama.is_available():
            return []
        running = self._ollama.list_running()
        return [self._ollama_entry_to_loaded(m) for m in running]

    def list_available(self) -> list[str]:
        """Modelos disponibles localmente en Ollama (en disco, no solo en VRAM)."""
        if not self._ollama.is_available():
            return []
        return [m["name"] for m in self._ollama.list_local()]

    def list_local_models(self) -> list[LocalModel]:
        """Modelos en disco con tamaño, parámetros y cuantización."""
        if not self._ollama.is_available():
            return []
        result = []
        for m in self._ollama.list_local():
            details = m.get("details") or {}
            size = m.get("size")
            result.append(LocalModel(
                model_id=m.get("name", ""),
                size_gib=round(size / _BYTES_PER_GIB, 2) if size else None,
                parameter_size=details.get("parameter_size"),
                quantization=details.get("quantization_level"),
                family=details.get("family"),
                modified_at=m.get("modified_at"),
            ))
        return result

    def ollama_available(self) -> bool:
        return self._ollama.is_available()

    def ollama_version(self) -> str | None:
        return self._ollama.version() if self._ollama.is_available() else None

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _require(self, backend: RuntimeBackend) -> None:
        if backend != RuntimeBackend.OLLAMA:
            raise RuntimeManagerError(f"Backend {backend.value!r} no implementado aún.")
        if not self._ollama.is_available():
            raise RuntimeManagerError(
                f"Ollama no está disponible en {self._ollama.base_url}. "
                "Ejecuta: ollama serve"
            )

    def _local_entry(self, model_id: str) -> dict | None:
        for m in self._ollama.list_local():
            if m.get("name") in (model_id, f"{model_id}:latest"):
                return m
        return None

    def _local_size_gib(self, model_id: str) -> float | None:
        entry = self._local_entry(model_id)
        size = entry.get("size") if entry else None
        return size / _BYTES_PER_GIB if size else None

    def _model_exists_locally(self, model_id: str) -> bool:
        return self._local_entry(model_id) is not None

    def _build_loaded_model(self, model_id: str, backend: RuntimeBackend) -> LoadedModel:
        running = self._ollama.list_running()
        for m in running:
            if m.get("name") == model_id or m.get("name") == f"{model_id}:latest":
                size_bytes = m.get("size_vram") or m.get("size") or 0
                return LoadedModel(
                    model_id=model_id,
                    backend=backend,
                    size_vram_gib=round(size_bytes / _BYTES_PER_GIB, 2) if size_bytes else None,
                    details=m,
                )
        return LoadedModel(model_id=model_id, backend=backend, size_vram_gib=None)

    @staticmethod
    def _ollama_entry_to_loaded(entry: dict) -> LoadedModel:
        size_bytes = entry.get("size_vram") or entry.get("size") or 0
        return LoadedModel(
            model_id=entry.get("name", ""),
            backend=RuntimeBackend.OLLAMA,
            size_vram_gib=round(size_bytes / _BYTES_PER_GIB, 2) if size_bytes else None,
            details=entry,
        )
