"""Ejecutar comandos: carpeta fija, tiempo límite, salida acotada y entorno limpio."""

from __future__ import annotations

import sys

import pytest

from core.code.shell import (
    MAX_OUTPUT_BYTES,
    ShellError,
    clamp_output,
    detect_shell,
    run,
    safe_env,
)


def py(codigo: str) -> str:
    """Un comando que existe en Windows, Linux y el Jetson: este mismo Python."""
    return f'"{sys.executable}" -c "{codigo}"'


# --- Entorno ----------------------------------------------------------------


def test_las_claves_no_viajan_al_proceso(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secreta")
    monkeypatch.setenv("MI_TOKEN_DE_ALGO", "secreta")
    monkeypatch.setenv("AWS_SESSION", "secreta")
    monkeypatch.setenv("PROYECTO", "magnus")
    entorno = safe_env()
    assert "OPENAI_API_KEY" not in entorno
    assert "MI_TOKEN_DE_ALGO" not in entorno
    assert "AWS_SESSION" not in entorno
    assert entorno["PROYECTO"] == "magnus"


def test_el_comando_no_ve_la_clave(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPER_API_KEY", "no-deberia-verse")
    r = run(py("import os;print(os.environ.get('SUPER_API_KEY','(sin clave)'))"), cwd=tmp_path)
    assert "(sin clave)" in r.output


# --- Salida -----------------------------------------------------------------


def test_recorte_por_el_medio():
    texto, recortada = clamp_output("a" * 100 + "b" * 100, limit=100)
    assert recortada
    assert texto.startswith("a") and texto.endswith("b")
    assert "se quitaron" in texto


def test_salida_corta_no_se_toca():
    texto, recortada = clamp_output("hola")
    assert texto == "hola" and not recortada


def test_salida_enorme_se_acota(tmp_path):
    r = run(py("print('x'*500000)"), cwd=tmp_path, max_output=4096)
    assert r.truncated
    assert len(r.output.encode()) < MAX_OUTPUT_BYTES


# --- Ejecución --------------------------------------------------------------


def test_comando_normal(tmp_path):
    r = run(py("print('hola magnus')"), cwd=tmp_path)
    assert r.ok
    assert "hola magnus" in r.output
    assert r.exit_code == 0
    assert "salida 0" in r.summary()


def test_codigo_de_salida_distinto_de_cero(tmp_path):
    """El código real del programa, no el del intérprete: así se sabe si un test falló."""
    r = run(py("import sys;sys.exit(3)"), cwd=tmp_path)
    assert not r.ok
    assert r.exit_code == 3


def test_los_errores_tambien_llegan(tmp_path):
    r = run(py("import sys;print('malo', file=sys.stderr)"), cwd=tmp_path)
    assert "malo" in r.output


def test_corre_en_la_carpeta_del_proyecto(tmp_path):
    (tmp_path / "marca.txt").write_text("aquí", encoding="utf-8")
    r = run(py("import os;print(os.listdir('.'))"), cwd=tmp_path)
    assert "marca.txt" in r.output


def test_tiempo_limite_corta_y_lo_dice(tmp_path):
    r = run(py("import time;time.sleep(30)"), cwd=tmp_path, timeout_s=2)
    assert r.timed_out
    assert not r.ok
    assert "cortó el comando" in r.output
    assert r.duration_s < 20  # no esperó los 30 segundos


def test_un_comando_que_pide_entrada_no_se_cuelga(tmp_path):
    r = run(py("input('dame algo: ')"), cwd=tmp_path, timeout_s=10)
    assert not r.timed_out  # stdin cerrado: falla rápido en vez de esperar


def test_salida_en_vivo(tmp_path):
    vistas: list[str] = []
    run(py("print('uno');print('dos')"), cwd=tmp_path, on_output=vistas.append)
    assert "".join(vistas).count("\n") >= 2


def test_comando_vacio(tmp_path):
    with pytest.raises(ShellError, match="vacío"):
        run("   ", cwd=tmp_path)


def test_carpeta_inexistente(tmp_path):
    with pytest.raises(ShellError, match="no existe"):
        run("echo hola", cwd=tmp_path / "no-existe")


def test_se_detecta_un_interprete_del_sistema():
    shell, prefijo = detect_shell()
    assert prefijo and isinstance(prefijo[0], str)
    assert shell.value in ("posix", "powershell")
