"""Skills: instrucciones reutilizables que el usuario crea, edita y recarga en caliente.

Formato, con el mismo espíritu que las skills de Claude Code:

    skills/<nombre>/SKILL.md

    ---
    name: resumir
    description: Resume textos largos en viñetas.
    triggers: [resume, resumen, tl;dr]
    tools: []
    ---
    (cuerpo en Markdown: las instrucciones que recibe el modelo)

Dos orígenes: las incluidas con Magnus (`skills/` del repo) y las del usuario
(`<carpeta de datos>/skills`). Si coinciden en nombre gana la del usuario, así
se puede ajustar una incluida sin tocar el repo.

Recarga en caliente sin vigilar archivos: cada consulta compara las fechas de
modificación; editar un SKILL.md surte efecto en el siguiente mensaje.

Cuándo se aplica una skill a un mensaje:
- invocación explícita: el mensaje empieza con `/nombre`;
- por disparador: una de sus `triggers` aparece como palabra en el mensaje
  (sin distinguir mayúsculas ni acentos).
"""

from __future__ import annotations

import re
import shutil
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

SKILL_FILE = "SKILL.md"
# Skills incluidas con Magnus: carpeta `skills/` en la raíz del repo (y de la imagen).
BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.DOTALL)
_INVOCATION_RE = re.compile(r"^\s*/([a-z0-9][a-z0-9-]{0,63})(?:\s+|$)")
_MAX_DESCRIPTION = 300


class SkillError(ValueError):
    """Skill inválida o que no se puede guardar. El mensaje va al usuario."""


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    triggers: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    source: str = "user"         # "builtin" | "user"
    path: str | None = None

    def to_dict(self, include_body: bool = True) -> dict:
        data = {
            "name": self.name,
            "description": self.description,
            "triggers": list(self.triggers),
            "tools": list(self.tools),
            "source": self.source,
            "path": self.path,
        }
        if include_body:
            data["body"] = self.body
        return data


def normalize(text: str) -> str:
    """Minúsculas y sin acentos, para comparar disparadores."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _as_str_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise SkillError(f"'{field_name}' debe ser una lista de textos.")
    return tuple(v.strip() for v in value if v.strip())


def build_skill(
    name: object,
    description: object,
    body: object,
    triggers: object = None,
    tools: object = None,
    *,
    source: str = "user",
    path: str | None = None,
) -> Skill:
    """Valida los campos y construye la skill."""
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise SkillError(
            "El nombre debe ir en minúsculas, con letras, números y guiones (máx. 64): "
            f"{name!r}"
        )
    if not isinstance(description, str) or not description.strip():
        raise SkillError("Falta la descripción: dice para qué sirve la skill.")
    if len(description) > _MAX_DESCRIPTION:
        raise SkillError(f"La descripción pasa de {_MAX_DESCRIPTION} caracteres.")
    if not isinstance(body, str) or not body.strip():
        raise SkillError("El cuerpo está vacío: son las instrucciones que recibe el modelo.")
    return Skill(
        name=name,
        description=description.strip(),
        body=body.strip() + "\n",
        triggers=_as_str_tuple(triggers, "triggers"),
        tools=_as_str_tuple(tools, "tools"),
        source=source,
        path=path,
    )


def parse_skill(text: str, *, source: str = "user", path: str | None = None) -> Skill:
    """SKILL.md → Skill. Lanza SkillError con un mensaje para el usuario."""
    match = _FRONTMATTER_RE.match(text.lstrip("﻿"))
    if not match:
        raise SkillError("Falta el encabezado YAML entre dos líneas '---'.")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise SkillError(f"El encabezado YAML no es válido: {exc}") from exc
    if not isinstance(meta, dict):
        raise SkillError("El encabezado debe ser una lista de 'clave: valor'.")
    return build_skill(meta.get("name"), meta.get("description"), match.group(2),
                       meta.get("triggers"), meta.get("tools"), source=source, path=path)


def render_skill(skill: Skill) -> str:
    """Skill → texto de SKILL.md."""
    meta = {
        "name": skill.name,
        "description": skill.description,
        "triggers": list(skill.triggers),
        "tools": list(skill.tools),
    }
    header = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{header}\n---\n\n{skill.body}"


def compose_system_prompt(base: str | None, skills: list[Skill]) -> str | None:
    """Une el system prompt del usuario con las instrucciones de las skills activas."""
    parts = [base.strip()] if base and base.strip() else []
    parts += [f"## Skill: {s.name}\n{s.description}\n\n{s.body.strip()}" for s in skills]
    return "\n\n".join(parts) if parts else None


class SkillRegistry:
    """Skills disponibles, con recarga en caliente. Seguro entre hilos."""

    def __init__(self, user_dir: Path, builtin_dir: Path | None = None) -> None:
        self.user_dir = Path(user_dir)
        self.builtin_dir = Path(builtin_dir) if builtin_dir else None
        self._lock = threading.Lock()
        self._skills: dict[str, Skill] = {}
        self._errors: dict[str, str] = {}
        self._signature: tuple = ()
        self._loaded = False

    # --- lectura ------------------------------------------------------------

    def _files(self) -> list[tuple[str, Path]]:
        found = []
        # Primero las incluidas: las del usuario se procesan después y las pisan.
        for source, folder in (("builtin", self.builtin_dir), ("user", self.user_dir)):
            if folder and folder.is_dir():
                found += [(source, f) for f in sorted(folder.glob(f"*/{SKILL_FILE}"))]
        return found

    def _signature_of(self, files: list[tuple[str, Path]]) -> tuple:
        sig = []
        for _, f in files:
            try:
                sig.append((str(f), f.stat().st_mtime_ns))
            except OSError:
                continue
        return tuple(sig)

    def reload(self) -> dict[str, str]:
        """Relee todo del disco. Devuelve los errores por carpeta."""
        with self._lock:
            return self._reload_locked()

    def _reload_locked(self) -> dict[str, str]:
        files = self._files()
        skills: dict[str, Skill] = {}
        errors: dict[str, str] = {}
        for source, f in files:
            folder = f.parent.name
            try:
                skill = parse_skill(f.read_text(encoding="utf-8"), source=source, path=str(f))
            except (OSError, UnicodeDecodeError, SkillError) as exc:
                errors[folder] = str(exc)
                continue
            if skill.name != folder:
                errors[folder] = f"El nombre '{skill.name}' no coincide con la carpeta '{folder}'."
                continue
            skills[skill.name] = skill
        self._skills, self._errors = skills, errors
        self._signature = self._signature_of(files)
        self._loaded = True
        return dict(errors)

    def _refresh(self) -> None:
        with self._lock:
            if not self._loaded or self._signature_of(self._files()) != self._signature:
                self._reload_locked()

    def list(self) -> list[Skill]:
        self._refresh()
        return sorted(self._skills.values(), key=lambda s: s.name)

    def get(self, name: str) -> Skill | None:
        self._refresh()
        return self._skills.get(name)

    @property
    def errors(self) -> dict[str, str]:
        self._refresh()
        return dict(self._errors)

    # --- escritura ------------------------------------------------------------

    def save(self, skill: Skill) -> Skill:
        """Crea o reemplaza una skill del usuario."""
        folder = self.user_dir / skill.name
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / SKILL_FILE
        path.write_text(render_skill(skill), encoding="utf-8")
        self.reload()
        saved = self.get(skill.name)
        if saved is None:  # no debería pasar: se validó al construirla
            raise SkillError(self._errors.get(skill.name, "No se pudo guardar la skill."))
        return saved

    def delete(self, name: str) -> bool:
        """Borra una skill del usuario. Las incluidas no se borran: se sobreescriben."""
        folder = self.user_dir / name
        if not _NAME_RE.match(name) or not (folder / SKILL_FILE).is_file():
            if self.get(name) is not None:
                raise SkillError(
                    f"'{name}' viene incluida con Magnus y no se puede borrar. "
                    "Crea una skill con el mismo nombre para cambiarla."
                )
            return False
        shutil.rmtree(folder)
        self.reload()
        return True

    # --- aplicación -----------------------------------------------------------

    def resolve(self, message: str) -> list[Skill]:
        """Skills que aplican a un mensaje: la invocada con /nombre, o las de sus disparadores."""
        invoked = _INVOCATION_RE.match(message)
        if invoked:
            skill = self.get(invoked.group(1))
            if skill:
                return [skill]
        text = normalize(message)
        matched = []
        for skill in self.list():
            for trigger in skill.triggers:
                pattern = r"(?<!\w)" + re.escape(normalize(trigger)) + r"(?!\w)"
                if re.search(pattern, text):
                    matched.append(skill)
                    break
        return matched

    def strip_invocation(self, message: str) -> str:
        """Quita el `/nombre` inicial si corresponde a una skill existente."""
        invoked = _INVOCATION_RE.match(message)
        if invoked and self.get(invoked.group(1)):
            return message[invoked.end():].strip() or message.strip()
        return message
