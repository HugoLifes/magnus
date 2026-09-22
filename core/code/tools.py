"""Herramientas de Magnus Code: leer, listar, buscar, editar y escribir.

Cada herramienta pasa **siempre** por la política de permisos antes de tocar
nada (`core/code/permissions.py`), y ninguna sale de la carpeta del proyecto.
Son pocas a propósito: un modelo local de 7–30 B se pierde con catálogos
grandes, y con cinco herramientas bien hechas se resuelve casi todo.

Dos decisiones que vienen de la investigación (`docs/MAGNUS_CODE.md`):

- **Buscar antes que indexar.** `search` usa ripgrep si está, y si no, un
  recorrido propio. Siempre ve el código de ahora, sin índice que mantener.
- **Editar por reemplazo exacto.** `edit` exige que el texto viejo aparezca una
  sola vez; si no, devuelve un error que el modelo puede corregir. Es el formato
  que mejor aplican los modelos, por encima del diff unificado.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from core.code.permissions import Action, Decision, Policy, Verdict

# Un archivo más grande que esto no cabe en el contexto de un modelo local.
MAX_READ_BYTES = 400 * 1024
MAX_MATCHES = 200
MAX_LINE_CHARS = 400

# Carpetas que nunca interesan y que harían lentísima cualquier búsqueda.
IGNORED_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "build", "dist", ".dart_tool", ".gradle", "target", ".next", ".idea", ".vscode",
})


class ToolError(Exception):
    """Falla una herramienta. El mensaje vuelve al modelo para que corrija."""


class PermissionRequired(ToolError):
    """La acción necesita permiso del usuario. Lleva el veredicto para la tarjeta."""

    def __init__(self, verdict: Verdict, action: Action, target: str) -> None:
        super().__init__(f"Necesita permiso ({verdict.risk.value}): {verdict.reason}")
        self.verdict = verdict
        self.action = action
        self.target = target


@dataclass
class ToolContext:
    """Dónde trabaja el agente y con qué permisos."""

    root: Path
    policy: Policy
    # Lo que ya aprobó el usuario en esta sesión: "editar:src/app.py".
    approved: set[str] = field(default_factory=set)

    def resolve(self, target: str) -> Path:
        """Ruta absoluta dentro del proyecto, o error si se sale."""
        path = Path(target)
        full = (self.root / path).resolve() if not path.is_absolute() else path.resolve()
        return full

    def check(self, action: Action, target: str) -> None:
        """Aplica la política. Lanza si se deniega o si hace falta preguntar."""
        if f"{action.value}:{target}" in self.approved:
            return
        verdict = self.policy.decide(action, target)
        if verdict.decision is Decision.DENY:
            raise ToolError(verdict.reason)
        if verdict.decision is Decision.ASK:
            raise PermissionRequired(verdict, action, target)

    def approve(self, action: Action, target: str) -> None:
        """Recuerda que el usuario dijo que sí a esto, en esta sesión."""
        self.approved.add(f"{action.value}:{target}")


# ---------------------------------------------------------------------------
# Leer
# ---------------------------------------------------------------------------


def read_file(ctx: ToolContext, target: str, *, start: int = 1, end: int | None = None) -> str:
    """Contenido de un archivo con números de línea, para poder editar después."""
    ctx.check(Action.READ, target)
    path = ctx.resolve(target)
    if not path.is_file():
        raise ToolError(f"No existe el archivo: {target}")
    size = path.stat().st_size
    if size > MAX_READ_BYTES:
        raise ToolError(
            f"{target} pesa {size // 1024} KiB y el límite es {MAX_READ_BYTES // 1024} KiB. "
            "Lee un rango de líneas o busca dentro con `buscar`."
        )
    data = path.read_bytes()
    if b"\0" in data[:4096]:
        raise ToolError(f"{target} es binario: no se puede leer como texto.")
    lineas = data.decode("utf-8", errors="replace").splitlines()
    fin = len(lineas) if end is None else min(end, len(lineas))
    if start < 1 or start > max(len(lineas), 1):
        raise ToolError(f"{target} tiene {len(lineas)} líneas; pediste desde la {start}.")
    trozo = lineas[start - 1:fin]
    ancho = len(str(fin))
    return "\n".join(f"{i:>{ancho}}  {linea}" for i, linea in enumerate(trozo, start))


def list_files(ctx: ToolContext, pattern: str = "**/*", *, limit: int = MAX_MATCHES) -> list[str]:
    """Archivos del proyecto que encajan con el patrón, sin carpetas de ruido."""
    ctx.check(Action.READ, pattern.split("*")[0] or ".")
    encontrados: list[str] = []
    for path in sorted(ctx.root.glob(pattern)):
        if not path.is_file() or _ignored(path, ctx.root):
            continue
        encontrados.append(path.relative_to(ctx.root).as_posix())
        if len(encontrados) >= limit:
            break
    return encontrados


def _ignored(path: Path, root: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.relative_to(root).parts[:-1])


# ---------------------------------------------------------------------------
# Buscar
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Match:
    """Una coincidencia: archivo, línea y el texto recortado."""

    path: str
    line: int
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.text}"


def search(ctx: ToolContext, query: str, *, glob: str | None = None,
           limit: int = MAX_MATCHES, regex: bool = False) -> list[Match]:
    """Busca texto en el proyecto. Usa ripgrep si está; si no, recorre los archivos.

    Se busca en el código tal como está en el disco: no hay índice que se quede
    viejo entre un commit y el siguiente.
    """
    if not query.strip():
        raise ToolError("La búsqueda está vacía.")
    ctx.check(Action.READ, glob or ".")
    rg = shutil.which("rg")
    if rg:
        return _search_ripgrep(rg, ctx, query, glob, limit, regex)
    return _search_python(ctx, query, glob, limit, regex)


def _search_ripgrep(rg: str, ctx: ToolContext, query: str, glob: str | None,
                    limit: int, regex: bool) -> list[Match]:
    cmd = [rg, "--line-number", "--no-heading", "--color", "never", "--max-count", str(limit)]
    if not regex:
        cmd.append("--fixed-strings")
    if glob:
        cmd += ["--glob", glob]
    cmd += ["--", query, str(ctx.root)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolError(f"No se pudo buscar: {exc}") from exc
    if out.returncode not in (0, 1):  # 1 = sin coincidencias
        raise ToolError(f"La búsqueda falló: {out.stderr.strip()[:200]}")
    return _parse_rg(out.stdout, ctx.root, limit)


def _parse_rg(salida: str, root: Path, limit: int) -> list[Match]:
    matches: list[Match] = []
    for linea in salida.splitlines():
        partes = linea.split(":", 2)
        if len(partes) < 3:
            continue
        archivo, numero, texto = partes
        # En Windows la ruta trae la unidad: "D:\proy\src:12:texto".
        if len(archivo) == 1 and numero.startswith("\\"):
            continue
        try:
            path = Path(archivo).resolve().relative_to(root).as_posix()
        except ValueError:
            path = archivo
        try:
            n = int(numero)
        except ValueError:
            continue
        matches.append(Match(path, n, texto.strip()[:MAX_LINE_CHARS]))
        if len(matches) >= limit:
            break
    return matches


def _search_python(ctx: ToolContext, query: str, glob: str | None,
                   limit: int, regex: bool) -> list[Match]:
    patron = re.compile(query if regex else re.escape(query))
    matches: list[Match] = []
    for path in sorted(ctx.root.glob(glob or "**/*")):
        if not path.is_file() or _ignored(path, ctx.root):
            continue
        try:
            if path.stat().st_size > MAX_READ_BYTES:
                continue
            data = path.read_bytes()
            if b"\0" in data[:4096]:
                continue
            texto = data.decode("utf-8", errors="replace")
        except OSError:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            if patron.search(linea):
                matches.append(Match(path.relative_to(ctx.root).as_posix(), n,
                                     linea.strip()[:MAX_LINE_CHARS]))
                if len(matches) >= limit:
                    return matches
    return matches


# ---------------------------------------------------------------------------
# Editar y escribir
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EditResult:
    """Qué cambió: para la vista de cambios y para el punto de control."""

    path: str
    line: int
    removed: int
    added: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line} · −{self.removed} +{self.added} líneas"


def edit_file(ctx: ToolContext, target: str, old: str, new: str) -> EditResult:
    """Reemplaza un bloque exacto. Falla si no aparece exactamente una vez."""
    if not old:
        raise ToolError("El texto a reemplazar está vacío: usa `escribir` para crear el archivo.")
    if old == new:
        raise ToolError("El texto viejo y el nuevo son iguales: no hay nada que cambiar.")
    ctx.check(Action.EDIT, target)
    path = ctx.resolve(target)
    if not path.is_file():
        raise ToolError(f"No existe el archivo: {target}")

    contenido = path.read_text(encoding="utf-8", errors="strict")
    apariciones = contenido.count(old)
    if apariciones == 0:
        raise ToolError(
            f"Ese texto no está en {target} tal cual. Lee el archivo y copia el bloque exacto, "
            "con su sangría."
        )
    if apariciones > 1:
        raise ToolError(
            f"Ese texto aparece {apariciones} veces en {target}. Incluye más líneas alrededor "
            "para que sea único."
        )

    linea = contenido[:contenido.index(old)].count("\n") + 1
    nuevo = contenido.replace(old, new, 1)
    _write(path, nuevo)
    return EditResult(target, linea, old.count("\n") + 1, new.count("\n") + 1)


def write_file(ctx: ToolContext, target: str, content: str) -> EditResult:
    """Crea o reemplaza un archivo entero."""
    path = ctx.resolve(target)
    ctx.check(Action.EDIT if path.exists() else Action.WRITE, target)
    antes = 0
    if path.exists():
        antes = path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, content)
    return EditResult(target, 1, antes, content.count("\n") + 1)


def _write(path: Path, contenido: str) -> None:
    """Escritura atómica: si falla a medias, el archivo original sigue entero."""
    temporal = path.with_suffix(path.suffix + ".magnus-tmp")
    try:
        temporal.write_text(contenido, encoding="utf-8", newline="")
        os.replace(temporal, path)
    finally:
        temporal.unlink(missing_ok=True)
