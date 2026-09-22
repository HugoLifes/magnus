"""Permisos de Magnus Code: qué puede hacer el agente y qué tiene que preguntar.

Dos puertas distintas protegen el equipo. Esta es la primera: **decide si una
acción se permite, se pregunta o se deniega**. La segunda es el sandbox, que
limita lo que un comando ya autorizado puede tocar (`core/code/sandbox/`).

El orden de evaluación es el mismo que usa Claude Code: **denegar → preguntar →
permitir**. Una denegación no se puede anular con un permiso más abajo, y las
reglas de la organización mandan sobre las del usuario.

Tres cosas que no dependen del modo elegido:

- **Los secretos no se leen.** `.env`, llaves SSH y credenciales están denegados
  siempre; que el modelo los pida es justo la señal de que algo va mal.
- **Fuera del proyecto no se escribe.** Leer fuera pregunta; escribir, no.
- **Lo destructivo siempre pregunta**, incluso en modo autónomo, y una lista
  corta de barbaridades queda bloqueada sin opción.

La clasificación de comandos **parsea**, no busca cadenas sueltas: un comando que
no se puede inspeccionar del todo (`eval`, `Invoke-Expression`, `-EncodedCommand`)
se marca como opaco y se pregunta, que es lo que hace Codex en Windows.
"""

from __future__ import annotations

import enum
import re
import shlex
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath


class Mode(str, enum.Enum):
    """Cuánta libertad tiene el agente en esta sesión."""

    PLAN = "plan"                     # solo lee y propone
    ASK = "preguntar"                 # por omisión: editar y ejecutar piden permiso
    EDIT = "aceptar_ediciones"        # edita libre en el proyecto; comandos preguntan
    AUTO = "autonomo"                 # solo con sandbox activo


class Action(str, enum.Enum):
    READ = "leer"
    EDIT = "editar"
    WRITE = "escribir"
    COMMAND = "comando"
    WEB = "web"


class Decision(str, enum.Enum):
    ALLOW = "permitir"
    ASK = "preguntar"
    DENY = "denegar"


class Risk(str, enum.Enum):
    """Qué puede pasar si esto corre."""

    READ = "lectura"
    WRITE_PROJECT = "escritura_proyecto"
    NETWORK = "red"
    OUTSIDE = "fuera_del_proyecto"
    DESTRUCTIVE = "destructivo"
    OPAQUE = "opaco"                  # no se puede inspeccionar: se pregunta
    UNKNOWN = "desconocido"


class Shell(str, enum.Enum):
    POSIX = "posix"
    POWERSHELL = "powershell"


class Source(str, enum.Enum):
    """Quién puso la regla. La de la organización no se anula."""

    ORG = "empresa"
    USER = "usuario"
    PROJECT = "proyecto"


# --- Secretos: se deniegan siempre, los pida quien los pida ------------------
SECRET_PATTERNS = (
    ".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "*.p12", "*.pfx",
    ".ssh/*", ".aws/credentials", ".config/gcloud/*", "*.keystore", "*secrets*.json",
)

# --- Comandos: listas de referencia -----------------------------------------
_BLOCKED = (
    # Barbaridades sin vuelta atrás: ni preguntando.
    re.compile(r"\brm\s+(-[a-z]*\s+)*-[a-z]*[rf][a-z]*\s+/(\s|$)"),
    re.compile(r"\bmkfs(\.|\s)"),
    re.compile(r"\bdd\b.*\bof=/dev/(sd|nvme|disk)"),
    re.compile(r"\bFormat-Volume\b", re.IGNORECASE),
    re.compile(r"\bClear-Disk\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{.*\};\s*:"),  # fork bomb
)

_DESTRUCTIVE = (
    re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rf]"),
    re.compile(r"\bshred\b"), re.compile(r"\bdd\b"), re.compile(r"\btruncate\b"),
    re.compile(r"\bgit\s+push\b.*(--force|-f\b)"),
    re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f)"),
    re.compile(r"\bdocker\s+(system\s+prune|volume\s+rm)"),
    re.compile(r"\b(shutdown|reboot|halt)\b"),
    re.compile(r"\bRemove-Item\b.*(-Recurse|-Force)", re.IGNORECASE),
    re.compile(r"\bremove-item\b\s+[^|]*\*", re.IGNORECASE),
    re.compile(r"\b(Stop|Restart)-Computer\b", re.IGNORECASE),
    re.compile(r"\bSet-ItemProperty\b.*HK(LM|CU):", re.IGNORECASE),
    re.compile(r"\bnpm\s+publish\b"), re.compile(r"\bsudo\b"),
    re.compile(r"\bStart-Process\b.*-Verb\s+RunAs", re.IGNORECASE),
)

_OPAQUE = (
    re.compile(r"\beval\b"), re.compile(r"\bsource\b"), re.compile(r"(^|\s)\.\s+\S"),
    re.compile(r"\b(ba)?sh\s+-c\b"), re.compile(r"\|\s*(ba)?sh\b"),
    re.compile(r"`[^`]+`"), re.compile(r"\$\("),
    re.compile(r"\bbase64\b.*-d"),
    re.compile(r"\bInvoke-Expression\b|\biex\b", re.IGNORECASE),
    re.compile(r"-Enc(odedCommand)?\b", re.IGNORECASE),
    re.compile(r"\bAdd-Type\b", re.IGNORECASE),
)

_NETWORK = (
    re.compile(r"\b(curl|wget|nc|netcat|ssh|scp|rsync|ping|telnet)\b"),
    re.compile(r"\bgit\s+(push|pull|fetch|clone|remote)\b"),
    re.compile(r"\b(npm|pnpm|yarn|pip|pip3|uv|cargo|go|apt|apt-get|brew|winget|choco)\s+"
               r"(install|add|get|update|upgrade|publish|sync)\b"),
    re.compile(r"\bInvoke-(WebRequest|RestMethod)\b|\biwr\b|\birm\b", re.IGNORECASE),
    re.compile(r"\bStart-BitsTransfer\b", re.IGNORECASE),
)

_WRITES = (
    re.compile(r"\b(touch|mkdir|mv|cp|tee|ln|chmod|chown|patch)\b"),
    re.compile(r"\bsed\b.*-i"),
    re.compile(r">>?\s*\S"),
    re.compile(r"\b(New-Item|Copy-Item|Move-Item|Set-Content|Add-Content|Out-File)\b",
               re.IGNORECASE),
)

_READS = (
    re.compile(r"^\s*(ls|dir|cat|head|tail|grep|rg|find|wc|file|stat|pwd|echo|which|type)\b"),
    re.compile(r"^\s*git\s+(status|diff|log|show|branch|remote\s+-v)\b"),
    re.compile(r"^\s*(Get-\w+|Test-Path|Select-String)\b", re.IGNORECASE),
)

# Separadores que encadenan comandos: cada parte se clasifica aparte.
_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")


@dataclass(frozen=True)
class Rule:
    """Regla de permisos: `Comando(git status)` permitir, `Leer(.env)` denegar."""

    action: Action
    pattern: str
    decision: Decision
    source: Source = Source.USER

    def matches(self, action: Action, target: str) -> bool:
        if action is not self.action:
            return False
        target = target.replace("\\", "/")
        return fnmatch(target, self.pattern) or target.startswith(self.pattern.rstrip("*"))


@dataclass(frozen=True)
class Verdict:
    """Qué se hace y por qué. El motivo se le enseña al usuario tal cual."""

    decision: Decision
    reason: str
    risk: Risk = Risk.UNKNOWN
    rule: Rule | None = None

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


# ---------------------------------------------------------------------------
# Clasificación de comandos
# ---------------------------------------------------------------------------


def classify_command(command: str, shell: Shell = Shell.POSIX) -> Risk:
    """Riesgo de un comando. Ante la duda, el riesgo más alto de sus partes."""
    text = (command or "").strip()
    if not text:
        return Risk.UNKNOWN
    if any(p.search(text) for p in _BLOCKED):
        return Risk.DESTRUCTIVE
    # Lo opaco se mira sobre el comando entero y antes de partirlo: `curl … | sh`
    # deja de verse si primero se separa por la tubería.
    if shell is Shell.POSIX and not _parseable(text):
        return Risk.OPAQUE
    if any(p.search(text) for p in _OPAQUE):
        return Risk.OPAQUE
    partes = [p for p in _SPLIT.split(text) if p.strip()]
    if len(partes) > 1:
        return max((classify_command(p, shell) for p in partes), key=_severity)
    return _classify_single(text, shell)


def _parseable(text: str) -> bool:
    """False si ni siquiera se puede tokenizar (comillas sin cerrar)."""
    try:
        shlex.split(text)
    except ValueError:
        return False
    return True


def _classify_single(text: str, shell: Shell) -> Risk:
    if any(p.search(text) for p in _DESTRUCTIVE):
        return Risk.DESTRUCTIVE
    if any(p.search(text) for p in _NETWORK):
        return Risk.NETWORK
    if any(p.search(text) for p in _WRITES):
        return Risk.WRITE_PROJECT
    if any(p.search(text) for p in _READS):
        return Risk.READ
    return Risk.UNKNOWN


_SEVERITY = {
    Risk.READ: 0,
    Risk.UNKNOWN: 1,
    Risk.WRITE_PROJECT: 2,
    Risk.NETWORK: 3,
    Risk.OUTSIDE: 4,
    Risk.OPAQUE: 5,
    Risk.DESTRUCTIVE: 6,
}


def _severity(risk: Risk) -> int:
    return _SEVERITY.get(risk, 1)


def is_blocked(command: str) -> bool:
    """Comandos que no se ejecutan ni con permiso: formatear, borrar la raíz…"""
    return any(p.search(command or "") for p in _BLOCKED)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------


def within(root: Path, target: Path | str) -> bool:
    """True si `target` cae dentro de `root`, resolviendo enlaces y `..`."""
    try:
        base = Path(root).resolve()
        path = (base / target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
    except OSError:
        return False
    return path == base or base in path.parents


def is_secret(target: Path | str, root: Path | None = None) -> bool:
    """True si la ruta huele a secreto (`.env`, llaves, credenciales)."""
    path = Path(target)
    name = path.name
    try:
        relative = path.relative_to(root) if root and path.is_absolute() else path
    except ValueError:
        relative = path
    as_posix = PurePosixPath(str(relative).replace("\\", "/")).as_posix()
    return any(fnmatch(name, pat) or fnmatch(as_posix, pat) or fnmatch(f"*/{as_posix}", f"*/{pat}")
               for pat in SECRET_PATTERNS)


# ---------------------------------------------------------------------------
# Política
# ---------------------------------------------------------------------------


@dataclass
class Policy:
    """Las reglas de esta sesión, más el modo y la carpeta del proyecto."""

    project_root: Path
    mode: Mode = Mode.ASK
    rules: list[Rule] = field(default_factory=list)
    trusted_folder: bool = True
    sandbox: bool = False

    def decide(self, action: Action, target: str, *, shell: Shell = Shell.POSIX) -> Verdict:
        """Veredicto para una acción concreta sobre un objetivo concreto."""
        if action is Action.COMMAND:
            return self._decide_command(target, shell)
        return self._decide_path(action, target)

    # --- Rutas ---------------------------------------------------------
    def _decide_path(self, action: Action, target: str) -> Verdict:
        if action in (Action.READ, Action.EDIT, Action.WRITE) and is_secret(target,
                                                                           self.project_root):
            return Verdict(Decision.DENY, "Los secretos no se tocan: quita esa ruta o ábrela tú.",
                           Risk.DESTRUCTIVE if action is not Action.READ else Risk.READ)

        rule = self._matching_rule(action, target)
        if rule and rule.decision is Decision.DENY:
            return Verdict(Decision.DENY, f"Una regla de {rule.source.value} lo deniega.",
                           Risk.UNKNOWN, rule)

        outside = not within(self.project_root, target)
        if outside and action in (Action.EDIT, Action.WRITE):
            return Verdict(Decision.DENY, "Está fuera de la carpeta del proyecto.", Risk.OUTSIDE)

        if not self.trusted_folder and action is not Action.READ:
            return Verdict(Decision.DENY,
                           "Esta carpeta todavía no es de confianza: solo lectura.", Risk.OUTSIDE)

        if self.mode is Mode.PLAN and action is not Action.READ:
            return Verdict(Decision.ASK, "Modo Plan: propone, no toca.", Risk.WRITE_PROJECT)

        if action is Action.READ:
            if outside:
                return Verdict(Decision.ASK, "Es un archivo de fuera del proyecto.", Risk.OUTSIDE)
            return self._from_rule(rule, Decision.ALLOW, "Lectura dentro del proyecto.", Risk.READ)

        if action is Action.WEB:
            return self._from_rule(rule, Decision.ASK, "Salir a la red necesita permiso.",
                                   Risk.NETWORK)

        # Editar o escribir dentro del proyecto.
        libre = self.mode in (Mode.EDIT, Mode.AUTO)
        return self._from_rule(
            rule,
            Decision.ALLOW if libre else Decision.ASK,
            "Edición dentro del proyecto." if libre else "Cambiar archivos pide permiso.",
            Risk.WRITE_PROJECT,
        )

    # --- Comandos ------------------------------------------------------
    def _decide_command(self, command: str, shell: Shell) -> Verdict:
        if is_blocked(command):
            return Verdict(Decision.DENY, "Ese comando no se ejecuta nunca desde Magnus.",
                           Risk.DESTRUCTIVE)

        rule = self._matching_rule(Action.COMMAND, command)
        if rule and rule.decision is Decision.DENY:
            return Verdict(Decision.DENY, f"Una regla de {rule.source.value} lo deniega.",
                           Risk.UNKNOWN, rule)

        risk = classify_command(command, shell)

        if not self.trusted_folder:
            return Verdict(Decision.DENY, "Esta carpeta todavía no es de confianza.", risk)

        if self.mode is Mode.PLAN:
            return Verdict(Decision.ASK, "Modo Plan: no ejecuta.", risk)

        # Lo destructivo y lo que no se puede inspeccionar siempre preguntan,
        # aunque el modo sea autónomo y aunque haya una regla que lo permita.
        if risk in (Risk.DESTRUCTIVE, Risk.OPAQUE):
            motivo = ("Puede destruir datos." if risk is Risk.DESTRUCTIVE
                      else "No se puede inspeccionar qué ejecuta.")
            return Verdict(Decision.ASK, motivo, risk)

        if rule and rule.decision is Decision.ALLOW:
            return Verdict(Decision.ALLOW, f"Permitido por una regla de {rule.source.value}.",
                           risk, rule)

        if self.mode is Mode.AUTO:
            if not self.sandbox:
                return Verdict(Decision.ASK, "Modo autónomo sin sandbox: cada comando pregunta.",
                               risk)
            if risk is Risk.NETWORK:
                return Verdict(Decision.ASK, "Salir a la red necesita permiso.", risk)
            return Verdict(Decision.ALLOW, "Modo autónomo con sandbox.", risk)

        if risk is Risk.READ:
            return Verdict(Decision.ALLOW, "Solo lee.", risk)
        return Verdict(Decision.ASK, "Ejecutar comandos pide permiso.", risk)

    # --- Reglas --------------------------------------------------------
    def _matching_rule(self, action: Action, target: str) -> Rule | None:
        """La regla que manda: primero las denegaciones, y la empresa antes que nadie."""
        candidatas = [r for r in self.rules if r.matches(action, target)]
        if not candidatas:
            return None
        orden = {Decision.DENY: 0, Decision.ASK: 1, Decision.ALLOW: 2}
        fuente = {Source.ORG: 0, Source.PROJECT: 1, Source.USER: 2}
        return min(candidatas, key=lambda r: (orden[r.decision], fuente[r.source]))

    @staticmethod
    def _from_rule(rule: Rule | None, default: Decision, reason: str, risk: Risk) -> Verdict:
        if rule is not None and rule.decision is not Decision.DENY:
            return Verdict(rule.decision, f"Regla de {rule.source.value}.", risk, rule)
        return Verdict(default, reason, risk)


def parse_rule(text: str, source: Source = Source.USER) -> Rule:
    """Lee una regla escrita como `Comando(git status) permitir`."""
    match = re.match(r"^\s*(\w+)\(([^)]*)\)\s+(\w+)\s*$", text)
    if not match:
        raise ValueError(f"Regla inválida: {text!r}. Formato: Comando(git status) permitir")
    accion, patron, decision = match.groups()
    try:
        return Rule(Action(accion.lower()), patron.strip(), Decision(decision.lower()), source)
    except ValueError as exc:
        raise ValueError(f"Regla inválida: {text!r}. {exc}") from exc
