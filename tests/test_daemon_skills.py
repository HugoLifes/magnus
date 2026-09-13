"""Endpoints /skills. Corren SIN GPU."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import daemon.app as app_module
from core.skills import BUILTIN_SKILLS_DIR, SkillRegistry


@pytest.fixture
def client(tmp_path):
    registry = SkillRegistry(tmp_path / "skills", BUILTIN_SKILLS_DIR)
    app_module.api.dependency_overrides[app_module.get_skill_registry] = lambda: registry
    yield TestClient(app_module.api)
    app_module.api.dependency_overrides.clear()


def test_lista_incluye_las_incluidas(client):
    body = client.get("/skills").json()
    nombres = {s["name"] for s in body["skills"]}
    assert {"resumir", "traducir", "revisar-codigo"} <= nombres
    assert body["errors"] == {}
    assert "body" not in body["skills"][0]


def test_crear_ver_resolver_y_borrar(client):
    r = client.put("/skills/correo-formal", json={
        "description": "Redacta correos formales.",
        "body": "Usa usted, saludo y despedida.",
        "triggers": ["correo formal"],
    })
    assert r.status_code == 200 and r.json()["source"] == "user"

    assert client.get("/skills/correo-formal").json()["body"].startswith("Usa usted")
    assert client.post("/skills/resolve", json={"message": "Escribe un CORREO FORMAL"}).json() \
        == {"skills": ["correo-formal"]}

    assert client.delete("/skills/correo-formal").status_code == 200
    assert client.get("/skills/correo-formal").status_code == 404


def test_validacion_y_borrado_de_incluida(client):
    r = client.put("/skills/Nombre Malo", json={"description": "x", "body": "y"})
    assert r.status_code == 400 and "minúsculas" in r.json()["detail"]
    r = client.delete("/skills/resumir")
    assert r.status_code == 400 and "incluida" in r.json()["detail"]
    assert client.delete("/skills/no-existe").status_code == 404


def test_recargar(client):
    body = client.post("/skills/reload").json()
    assert "resumir" in body["skills"]
