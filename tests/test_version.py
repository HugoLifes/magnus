"""La versión es una sola: núcleo, paquete y app tienen que coincidir."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.version import __version__, is_prerelease, semver, tag

RAIZ = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("pep440,esperado", [
    ("0.9.0b1", "0.9.0-beta.1"),
    ("1.0.0", "1.0.0"),
    ("1.2.3a4", "1.2.3-alpha.4"),
    ("2.0.0rc2", "2.0.0-rc.2"),
])
def test_traduccion_a_semver(pep440, esperado):
    assert semver(pep440) == esperado


def test_etiqueta_de_git():
    assert tag("0.9.0b1") == "v0.9.0-beta.1"
    assert tag("1.0.0") == "v1.0.0"


def test_se_sabe_si_es_prelanzamiento():
    assert is_prerelease("0.9.0b1")
    assert is_prerelease("1.0.0a1")
    assert not is_prerelease("1.0.0")


def test_version_invalida():
    with pytest.raises(ValueError):
        semver("no-es-una-version")


def test_el_paquete_declara_la_misma_version():
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    declarada = re.search(r'^version = "([^"]+)"', texto, re.MULTILINE).group(1)
    assert declarada == __version__, "pyproject.toml y core/version.py no coinciden"


def test_la_app_declara_la_misma_version():
    texto = (RAIZ / "clients" / "desktop" / "pubspec.yaml").read_text(encoding="utf-8")
    declarada = re.search(r"^version: ([^\s+]+)", texto, re.MULTILINE).group(1)
    assert declarada == semver(), "pubspec.yaml y core/version.py no coinciden"


def test_el_daemon_no_repite_la_version_a_mano():
    """Si vuelve a aparecer escrita a mano, esto avisa antes de que se desincronice."""
    texto = (RAIZ / "daemon" / "app.py").read_text(encoding="utf-8")
    assert f'"{__version__}"' not in texto
