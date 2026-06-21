"""Gestión del ciclo de vida de modelos en runtimes de inferencia.

Expone una interfaz única — `serve()` / `stop()` / `list_loaded()` — que
hoy arranca y para modelos en Ollama (vía su HTTP API). La misma interfaz
servirá para vLLM sin cambiar el contrato hacia arriba.

Ollama se gestiona así:
  - Cargar   → POST /api/pull (si el modelo no está) + POST /api/generate
               con keep_alive=-1 para que Ollama no lo expulse de VRAM.
  - Descargar → DELETE /api/delete  (elimina el modelo de la cache local)
               O bien POST /api/generate con keep_alive=0 para liberarlo
               de VRAM sin borrarlo del disco.  Aquí se usa keep_alive=0
               porque es el flujo no destructivo.
  - Estado   → GET /api/ps  (modelos cargados en VRAM ahora mismo)
  - Listar   → GET /api/tags  (modelos disponibles localmente)

Todas las llamadas HTTP se hacen con httpx (sync); la dependencia ya está
en pyproject.toml.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

import httpx


class RuntimeBackend(str, enum.Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"


@dataclass
class LoadedModel:
    model_id: str
    backend: RuntimeBackend
    size_vram_gib: float | None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeManagerError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


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
            raise RuntimeManagerError(
                f"No se puede conectar con Ollama en {self.base_url}. "
                "¿Está arrancado? Ejecuta: ollama serve"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeManagerError(f"Ollama respondió {exc.response.status_code}: {exc.response.text}") from exc

    def _post(self, path: str, body: dict) -> Any:
        try:
            r = httpx.post(f"{self.base_url}{path}", json=body, timeout=300)
            r.raise_for_status()
            return r.json() if r.content else {}
        except httpx.ConnectError as exc:
            raise RuntimeManagerError(
                f"No se puede conectar con Ollama en {self.base_url}. "
                "¿Está arrancado? Ejecuta: ollama serve"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeManagerError(f"Ollama respondió {exc.response.status_code}: {exc.response.text}") from exc

    def _delete(self, path: str, body: dict) -> None:
        try:
            r = httpx.request("DELETE", f"{self.base_url}{path}", json=body, timeout=30)
            r.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeManagerError(
                f"No se puede conectar con Ollama en {self.base_url}. "
                "¿Está arrancado? Ejecuta: ollama serve"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeManagerError(f"Ollama respondió {exc.response.status_code}: {exc.response.text}") from exc

    def is_available(self) -> bool:
        try:
            httpx.get(f"{self.base_url}/", timeout=3)
            return True
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def list_local(self) -> list[dict]:
        """Modelos disponibles localmente (en disco)."""
        data = self._get("/api/tags")
        return data.get("models", [])

    def list_running(self) -> list[dict]:
        """Modelos cargados ahora mismo en VRAM (GET /api/ps)."""
        data = self._get("/api/ps")
        return data.get("models", [])

    def pull(self, model_id: str) -> None:
        """Descarga el modelo si Ollama no lo tiene todavía."""
        self._post("/api/pull", {"name": model_id, "stream": False})

    def load_into_vram(self, model_id: str) -> None:
        """Carga el modelo en VRAM con keep_alive=-1 (no expulsar)."""
        self._post("/api/generate", {"model": model_id, "prompt": "", "keep_alive": -1, "stream": False})

    def unload_from_vram(self, model_id: str) -> None:
        """Libera VRAM del modelo sin borrar los pesos del disco."""
        self._post("/api/generate", {"model": model_id, "prompt": "", "keep_alive": 0, "stream": False})

    def delete(self, model_id: str) -> None:
        """Elimina el modelo del disco local de Ollama."""
        self._delete("/api/delete", {"name": model_id})


class RuntimeManager:
    """Gestiona el ciclo de vida de modelos sobre uno o varios backends.

    Hoy solo usa Ollama. La misma interfaz pública (`serve`, `stop`,
    `list_loaded`, `list_available`) será implementada para vLLM más adelante.
    """

    def __init__(self, ollama_url: str = "http://127.0.0.1:11434") -> None:
        self._ollama = OllamaClient(ollama_url)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def serve(
        self,
        model_id: str,
        backend: RuntimeBackend = RuntimeBackend.OLLAMA,
        pull_if_missing: bool = True,
    ) -> LoadedModel:
        """Carga `model_id` en VRAM usando `backend`.

        Si `pull_if_missing=True` y Ollama no tiene el modelo localmente,
        lo descarga primero (puede tardar según el tamaño).

        Returns el `LoadedModel` con el estado tras la carga.
        Raises `RuntimeManagerError` si algo va mal.
        """
        if backend != RuntimeBackend.OLLAMA:
            raise RuntimeManagerError(f"Backend {backend.value!r} no implementado aún.")

        if not self._ollama.is_available():
            raise RuntimeManagerError(
                f"Ollama no está disponible en {self._ollama.base_url}. "
                "Ejecuta: ollama serve"
            )

        if pull_if_missing and not self._model_exists_locally(model_id):
            self._ollama.pull(model_id)

        self._ollama.load_into_vram(model_id)
        return self._build_loaded_model(model_id, backend)

    def stop(
        self,
        model_id: str,
        backend: RuntimeBackend = RuntimeBackend.OLLAMA,
        delete_local: bool = False,
    ) -> None:
        """Libera el modelo de VRAM.

        Con `delete_local=True` también borra los pesos del disco de Ollama.
        """
        if backend != RuntimeBackend.OLLAMA:
            raise RuntimeManagerError(f"Backend {backend.value!r} no implementado aún.")

        if not self._ollama.is_available():
            raise RuntimeManagerError(
                f"Ollama no está disponible en {self._ollama.base_url}."
            )

        self._ollama.unload_from_vram(model_id)
        if delete_local:
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

    def ollama_available(self) -> bool:
        return self._ollama.is_available()

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _model_exists_locally(self, model_id: str) -> bool:
        local = self._ollama.list_local()
        names = {m["name"] for m in local}
        # Ollama normaliza los nombres añadiendo ":latest" si no hay tag.
        return model_id in names or f"{model_id}:latest" in names

    def _build_loaded_model(self, model_id: str, backend: RuntimeBackend) -> LoadedModel:
        running = self._ollama.list_running()
        for m in running:
            if m.get("name") == model_id or m.get("name") == f"{model_id}:latest":
                size_bytes = m.get("size_vram") or m.get("size") or 0
                return LoadedModel(
                    model_id=model_id,
                    backend=backend,
                    size_vram_gib=round(size_bytes / 1024**3, 2) if size_bytes else None,
                    details=m,
                )
        return LoadedModel(model_id=model_id, backend=backend, size_vram_gib=None)

    @staticmethod
    def _ollama_entry_to_loaded(entry: dict) -> LoadedModel:
        size_bytes = entry.get("size_vram") or entry.get("size") or 0
        return LoadedModel(
            model_id=entry.get("name", ""),
            backend=RuntimeBackend.OLLAMA,
            size_vram_gib=round(size_bytes / 1024**3, 2) if size_bytes else None,
            details=entry,
        )
