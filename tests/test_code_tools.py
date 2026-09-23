"""Herramientas de Magnus Code: leer, listar, buscar, editar y escribir."""

from __future__ import annotations

import pytest

from core.code.permissions import Action, Mode, Policy
from core.code.tools import (
    MAX_READ_BYTES,
    PermissionRequired,
    ToolContext,
    ToolError,
    edit_file,
    list_files,
    read_file,
    search,
    write_file,
)


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def saludar(nombre):\n    return f'hola {nombre}'\n\n\nsaludar('mundo')\n",
        encoding="utf-8")
    (tmp_path / "src" / "util.py").write_text("VALOR = 42\n", encoding="utf-8")
    (tmp_path / ".env").write_text("CLAVE=secreta\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ruido.js").write_text("saludar()\n", encoding="utf-8")
    # Modo que edita sin preguntar, para no repetir aprobaciones en cada test.
    return ToolContext(root=tmp_path, policy=Policy(project_root=tmp_path, mode=Mode.EDIT))


# --- Leer -------------------------------------------------------------------


def test_leer_numera_las_lineas(ctx):
    texto = read_file(ctx, "src/app.py")
    assert texto.splitlines()[0].strip().startswith("1  def saludar")
    assert "5  saludar('mundo')" in texto


def test_leer_un_rango(ctx):
    texto = read_file(ctx, "src/app.py", start=2, end=2)
    assert texto.strip().startswith("2  ")
    assert "def saludar" not in texto


def test_leer_un_secreto_se_deniega(ctx):
    with pytest.raises(ToolError, match="secretos"):
        read_file(ctx, ".env")


def test_leer_algo_que_no_existe(ctx):
    with pytest.raises(ToolError, match="No existe"):
        read_file(ctx, "src/nada.py")


def test_leer_binario_avisa(ctx):
    (ctx.root / "imagen.bin").write_bytes(b"\x89PNG\x00\x00binario")
    with pytest.raises(ToolError, match="binario"):
        read_file(ctx, "imagen.bin")


def test_archivo_gigante_manda_a_buscar(ctx):
    (ctx.root / "grande.txt").write_text("x" * (MAX_READ_BYTES + 10), encoding="utf-8")
    with pytest.raises(ToolError, match="buscar"):
        read_file(ctx, "grande.txt")


def test_no_se_lee_fuera_del_proyecto(ctx):
    fuera = ctx.root.parent / "fuera.txt"
    fuera.write_text("secreto del vecino", encoding="utf-8")
    with pytest.raises(PermissionRequired):
        read_file(ctx, str(fuera))


# --- Listar y buscar --------------------------------------------------------


def test_listar_salta_el_ruido(ctx):
    archivos = list_files(ctx, "**/*.py")
    assert "src/app.py" in archivos and "src/util.py" in archivos
    assert not any("node_modules" in a for a in archivos)


def test_buscar_encuentra_con_archivo_y_linea(ctx):
    resultados = search(ctx, "def saludar")
    assert len(resultados) == 1
    assert resultados[0].path == "src/app.py"
    assert resultados[0].line == 1


def test_buscar_filtra_por_patron(ctx):
    assert search(ctx, "VALOR", glob="**/util.py")
    assert not search(ctx, "VALOR", glob="**/app.py")


def test_buscar_vacio_avisa(ctx):
    with pytest.raises(ToolError, match="vacía"):
        search(ctx, "   ")


def test_buscar_sin_coincidencias_devuelve_lista_vacia(ctx):
    assert search(ctx, "estoNoEstaEnNingunLado") == []


# --- Editar -----------------------------------------------------------------


def test_editar_reemplaza_y_dice_que_cambio(ctx):
    r = edit_file(ctx, "src/util.py", "VALOR = 42", "VALOR = 99")
    assert (ctx.root / "src" / "util.py").read_text(encoding="utf-8") == "VALOR = 99\n"
    assert r.line == 1 and r.path == "src/util.py"


def test_editar_algo_que_no_esta_explica_como_arreglarlo(ctx):
    with pytest.raises(ToolError, match="sangría"):
        edit_file(ctx, "src/util.py", "VALOR = 7", "VALOR = 8")


def test_editar_algo_ambiguo_pide_mas_contexto(ctx):
    (ctx.root / "src" / "dos.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    with pytest.raises(ToolError, match="2 veces"):
        edit_file(ctx, "src/dos.py", "x = 1", "x = 2")


def test_editar_sin_cambios_no_pasa(ctx):
    with pytest.raises(ToolError, match="iguales"):
        edit_file(ctx, "src/util.py", "VALOR = 42", "VALOR = 42")


def test_editar_en_modo_preguntar_pide_permiso(ctx):
    ctx.policy.mode = Mode.ASK
    with pytest.raises(PermissionRequired) as exc:
        edit_file(ctx, "src/util.py", "VALOR = 42", "VALOR = 99")
    assert exc.value.action is Action.EDIT
    # Con la aprobación del usuario, el mismo cambio sí entra.
    ctx.approve(Action.EDIT, "src/util.py")
    edit_file(ctx, "src/util.py", "VALOR = 42", "VALOR = 99")
    assert "99" in (ctx.root / "src" / "util.py").read_text(encoding="utf-8")


def test_escribir_crea_carpetas(ctx):
    write_file(ctx, "src/nuevo/modulo.py", "print('hola')\n")
    assert (ctx.root / "src" / "nuevo" / "modulo.py").exists()


def test_escribir_fuera_del_proyecto_se_deniega(ctx):
    with pytest.raises(ToolError, match="fuera de la carpeta"):
        write_file(ctx, str(ctx.root.parent / "intruso.txt"), "x")


def test_una_edicion_fallida_no_deja_archivos_temporales(ctx):
    with pytest.raises(ToolError):
        edit_file(ctx, "src/util.py", "no existe", "otra cosa")
    assert not list(ctx.root.rglob("*.magnus-tmp"))
