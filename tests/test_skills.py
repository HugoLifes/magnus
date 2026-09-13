"""Skills: formato, validación, recarga en caliente y resolución. Corren SIN GPU."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.skills import (
    Skill,
    SkillError,
    SkillRegistry,
    build_skill,
    compose_system_prompt,
    parse_skill,
    render_skill,
)

REPO_SKILLS = Path(__file__).resolve().parent.parent / "skills"

_RESUMIR = """---
name: resumir
description: Resume textos.
triggers: [resume, tl;dr]
---
Resume en viñetas.
"""


def _write(folder: Path, name: str, text: str) -> Path:
    path = folder / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_y_render_ida_y_vuelta():
    skill = parse_skill(_RESUMIR)
    assert skill.name == "resumir"
    assert skill.triggers == ("resume", "tl;dr")
    assert parse_skill(render_skill(skill)) == skill


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("sin encabezado", "encabezado YAML"),
        ("---\nname: [roto\n---\ncuerpo", "no es válido"),
        ("---\nname: Mayusculas\ndescription: x\n---\ncuerpo", "minúsculas"),
        ("---\nname: ok\n---\ncuerpo", "descripción"),
        ("---\nname: ok\ndescription: x\n---\n   ", "vacío"),
        ("---\nname: ok\ndescription: x\ntriggers: 5\n---\ncuerpo", "lista de textos"),
    ],
)
def test_validacion_con_mensajes_utiles(texto, mensaje):
    with pytest.raises(SkillError, match=mensaje):
        parse_skill(texto)


def test_trigger_suelto_como_texto():
    skill = build_skill("a", "b", "c", triggers="hola")
    assert skill.triggers == ("hola",)


def test_usuario_pisa_a_la_incluida(tmp_path):
    builtin, user = tmp_path / "builtin", tmp_path / "user"
    _write(builtin, "resumir", _RESUMIR)
    _write(user, "resumir", _RESUMIR.replace("Resume en viñetas.", "Resume en una frase."))
    reg = SkillRegistry(user, builtin)
    skill = reg.get("resumir")
    assert skill.source == "user" and "una frase" in skill.body


def test_recarga_en_caliente(tmp_path):
    reg = SkillRegistry(tmp_path)
    assert reg.list() == []
    path = _write(tmp_path, "resumir", _RESUMIR)
    assert [s.name for s in reg.list()] == ["resumir"]  # aparece sin reiniciar

    path.write_text(_RESUMIR.replace("Resume en viñetas.", "Nuevo cuerpo."), encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert "Nuevo cuerpo" in reg.get("resumir").body


def test_errores_por_carpeta_sin_romper_las_demas(tmp_path):
    _write(tmp_path, "resumir", _RESUMIR)
    _write(tmp_path, "rota", "sin encabezado")
    _write(tmp_path, "otra", _RESUMIR)  # nombre no coincide con la carpeta
    reg = SkillRegistry(tmp_path)
    assert [s.name for s in reg.list()] == ["resumir"]
    assert set(reg.errors) == {"rota", "otra"}
    assert "no coincide" in reg.errors["otra"]


def test_guardar_y_borrar(tmp_path):
    builtin = tmp_path / "builtin"
    _write(builtin, "traducir", _RESUMIR.replace("resumir", "traducir"))
    reg = SkillRegistry(tmp_path / "user", builtin)

    saved = reg.save(build_skill("mi-skill", "Hace algo", "Instrucciones", ["algo"]))
    assert saved.source == "user" and Path(saved.path).is_file()
    assert reg.delete("mi-skill") is True
    assert reg.get("mi-skill") is None
    assert reg.delete("no-existe") is False
    with pytest.raises(SkillError, match="incluida"):
        reg.delete("traducir")


def test_resolver_por_disparador_sin_acentos_y_por_invocacion(tmp_path):
    _write(tmp_path, "resumir", _RESUMIR)
    _write(tmp_path, "traducir", "---\nname: traducir\ndescription: t\n"
                                 "triggers: [traducción]\n---\nTraduce.\n")
    reg = SkillRegistry(tmp_path)

    assert [s.name for s in reg.resolve("Por favor RESUME este artículo")] == ["resumir"]
    assert [s.name for s in reg.resolve("haz una traduccion de esto")] == ["traducir"]
    assert reg.resolve("resumido no es disparador") == []  # palabra completa
    assert [s.name for s in reg.resolve("/traducir hola mundo")] == ["traducir"]
    assert reg.strip_invocation("/traducir hola mundo") == "hola mundo"
    assert reg.strip_invocation("/inexistente hola") == "/inexistente hola"


def test_componer_system_prompt():
    s = Skill("resumir", "Resume textos.", "Resume en viñetas.\n")
    prompt = compose_system_prompt("Sé breve.", [s])
    assert prompt.startswith("Sé breve.") and "## Skill: resumir" in prompt
    assert compose_system_prompt(None, []) is None


def test_skills_incluidas_son_validas():
    reg = SkillRegistry(Path("no-existe"), REPO_SKILLS)
    assert reg.errors == {}
    assert {"resumir", "traducir", "revisar-codigo"} <= {s.name for s in reg.list()}
