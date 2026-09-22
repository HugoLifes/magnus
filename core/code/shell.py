"""Ejecutar comandos desde Magnus Code, con correa corta.

Los permisos (`permissions.py`) deciden **si** un comando corre. Este módulo se
encarga de **cómo** corre, y de que no se quede colgado ni se lleve el equipo por
delante:

- **Carpeta fija**: siempre en la raíz del proyecto.
- **Tiempo límite**, y al agotarse se mata el proceso **y a sus hijos**: un
  `npm run dev` que arranca otros procesos no puede quedarse suelto.
- **Salida acotada**: si un comando escupe megas, se guarda el principio y el
  final y se avisa de lo que se quitó. El modelo no necesita más y el contexto
  no se llena de basura.
- **Entorno saneado**: las claves del sistema (`*_API_KEY`, `*_TOKEN`, `AWS_*`…)
  no se le pasan a un proceso que lanzó un modelo.

Todavía no usa pseudo-terminal (ConPTY en Windows, `pty` en Unix): los programas
que piden entrada interactiva se cortan con un mensaje claro en lugar de
quedarse esperando para siempre.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.code.permissions import Shell

DEFAULT_TIMEOUT_S = 120.0
MAX_OUTPUT_BYTES = 200 * 1024

# Nada de esto viaja a un proceso lanzado por el modelo.
_SECRET_ENV = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
_SECRET_PREFIXES = ("AWS_", "ANTHROPIC_", "OPENAI_", "GOOGLE_", "AZURE_", "GH_", "GITHUB_")


class ShellError(Exception):
    """No se pudo ni lanzar el comando."""


@dataclass(frozen=True)
class CommandResult:
    """Lo que pasó al ejecutar. `output` junta salida y errores, en orden."""

    command: str
    exit_code: int
    output: str
    duration_s: float
    timed_out: bool = False
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def summary(self) -> str:
        """Una línea para la bitácora y para el modelo."""
        estado = "agotó el tiempo" if self.timed_out else f"salida {self.exit_code}"
        return f"{self.command} · {estado} · {self.duration_s:.1f} s"


def detect_shell() -> tuple[Shell, list[str]]:
    """Qué intérprete usar aquí y cómo pasarle un comando.

    En Windows se prefiere PowerShell 7 (`pwsh`) y si no está, el 5.1 que trae el
    sistema. En Linux, macOS y Jetson, el shell del usuario o `bash`.
    """
    if platform.system() == "Windows":
        pwsh = shutil.which("pwsh")
        if pwsh:
            return Shell.POWERSHELL, [pwsh, "-NoProfile", "-NonInteractive", "-Command"]
        powershell = shutil.which("powershell") or "powershell"
        return Shell.POWERSHELL, [powershell, "-NoProfile", "-NonInteractive", "-Command"]
    shell = os.environ.get("SHELL") or shutil.which("bash") or "/bin/sh"
    return Shell.POSIX, [shell, "-c"]


def safe_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Copia del entorno sin claves ni credenciales."""
    entorno = dict(os.environ if base is None else base)
    for nombre in list(entorno):
        mayus = nombre.upper()
        if any(p in mayus for p in _SECRET_ENV) or mayus.startswith(_SECRET_PREFIXES):
            entorno.pop(nombre)
    return entorno


def clamp_output(texto: str, limit: int = MAX_OUTPUT_BYTES) -> tuple[str, bool]:
    """Recorta por el medio: el principio y el final son lo que dice algo."""
    data = texto.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return texto, False
    mitad = limit // 2
    quitado = len(data) - limit
    cabeza = data[:mitad].decode("utf-8", errors="ignore")
    cola = data[-mitad:].decode("utf-8", errors="ignore")
    return f"{cabeza}\n\n… se quitaron {quitado // 1024} KiB del medio …\n\n{cola}", True


def run(
    command: str,
    *,
    cwd: Path,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_output: int = MAX_OUTPUT_BYTES,
    on_output: Callable[[str], None] | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Ejecuta un comando en la carpeta del proyecto y devuelve lo que pasó.

    `on_output` recibe la salida según llega, para enseñarla en vivo en la app.
    """
    if not command.strip():
        raise ShellError("El comando está vacío.")
    cwd = Path(cwd)
    if not cwd.is_dir():
        raise ShellError(f"La carpeta del proyecto no existe: {cwd}")

    shell, prefijo = detect_shell()
    command = _for_shell(command, shell)
    inicio = time.monotonic()
    try:
        proceso = subprocess.Popen(
            [*prefijo, command],
            cwd=str(cwd),
            env=safe_env(env),
            stdin=subprocess.DEVNULL,  # nada interactivo: se corta, no se cuelga
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **_grupo_de_procesos(),
        )
    except OSError as exc:
        raise ShellError(f"No se pudo ejecutar: {exc}") from exc

    trozos: list[str] = []

    def leer() -> None:
        assert proceso.stdout is not None
        for linea in proceso.stdout:
            trozos.append(linea)
            if on_output:
                on_output(linea)

    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()

    timed_out = False
    try:
        proceso.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(proceso)
        proceso.wait(timeout=10)
    hilo.join(timeout=5)

    salida, recortada = clamp_output("".join(trozos), max_output)
    if timed_out:
        salida += (f"\n\n[Magnus cortó el comando a los {timeout_s:.0f} s "
                   "y cerró también sus procesos hijos.]")
    return CommandResult(
        command=command,
        exit_code=proceso.returncode if proceso.returncode is not None else -1,
        output=salida,
        duration_s=time.monotonic() - inicio,
        timed_out=timed_out,
        truncated=recortada,
    )


# PowerShell sale con 0 o 1 pase lo que pase: sin esto, un `npm test` que falla
# se ve como que pasó. Se propaga el código real del programa.
_PS_EXIT = '; exit $(if ($null -eq $LASTEXITCODE) { if ($?) { 0 } else { 1 } } else { $LASTEXITCODE })'


def _for_shell(command: str, shell: Shell) -> str:
    """Ajustes mínimos para que el intérprete entienda lo que se le manda.

    Dos cosas que solo pasan en PowerShell:

    - Un comando que empieza con comillas —una ruta con espacios, que es justo lo
      que genera un modelo— se trata como una cadena y se imprime en vez de
      ejecutarse. El operador de llamada (`&`) lo arregla.
    - El código de salida del programa no llega solo: hay que devolverlo a mano.
    """
    if shell is not Shell.POWERSHELL:
        return command
    if command.lstrip()[:1] in ('"', "'"):
        command = f"& {command}"
    return command + _PS_EXIT


def _grupo_de_procesos() -> dict:
    """Arranca el proceso en su propio grupo para poder matar el árbol entero."""
    if platform.system() == "Windows":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def kill_tree(proceso: subprocess.Popen) -> None:
    """Mata el proceso y a todos sus hijos. Sin esto, cancelar no cancela nada."""
    if proceso.poll() is not None:
        return
    if platform.system() == "Windows":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proceso.pid)],
                       capture_output=True, check=False)
        return
    import signal

    try:
        os.killpg(os.getpgid(proceso.pid), signal.SIGTERM)
        time.sleep(0.3)
        if proceso.poll() is None:
            os.killpg(os.getpgid(proceso.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proceso.kill()
