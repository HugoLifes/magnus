"""Token de acceso al daemon. Corren SIN GPU."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import daemon.app as app_module
from core.security import bind_error, generate_token, is_loopback, supplied_token, token_ok


@pytest.mark.parametrize(("host", "loop"), [
    ("127.0.0.1", True), ("localhost", True), ("::1", True),
    ("0.0.0.0", False), ("192.168.1.20", False), ("mi-servidor", False),
])
def test_loopback(host, loop):
    assert is_loopback(host) is loop


def test_bind_sin_token_fuera_de_loopback():
    assert bind_error("127.0.0.1", None) is None
    assert "magnus token new" in bind_error("0.0.0.0", None)
    assert bind_error("0.0.0.0", "secreto") is None


def test_formas_de_mandar_el_token():
    assert supplied_token({"authorization": "Bearer abc"}, {}) == "abc"
    assert supplied_token({"x-magnus-token": "abc"}, {}) == "abc"
    assert supplied_token({}, {"token": "abc"}) == "abc"
    assert supplied_token({}, {}) is None
    assert token_ok(None, {}, {}) is True
    assert token_ok("abc", {}, {"token": "abc"}) is True
    assert token_ok("abc", {"authorization": "Bearer otro"}, {}) is False


def test_tokens_distintos_y_largos():
    a, b = generate_token(), generate_token()
    assert a != b and len(a) >= 40


@pytest.fixture
def con_token(monkeypatch, tmp_path):
    monkeypatch.setenv("MAGNUS_HOME", str(tmp_path))
    monkeypatch.setenv("MAGNUS_API_TOKEN", "secreto-de-prueba")
    app_module.get_settings.cache_clear()
    yield TestClient(app_module.api)
    app_module.get_settings.cache_clear()


def test_daemon_exige_token(con_token, monkeypatch):
    client = con_token
    monkeypatch.setattr(app_module, "detect_platform", lambda: _FakeProfile())
    assert client.get("/platform").status_code == 401
    assert client.get("/platform", headers={"Authorization": "Bearer malo"}).status_code == 401
    ok = client.get("/platform", headers={"Authorization": "Bearer secreto-de-prueba"})
    assert ok.status_code == 200
    assert client.get("/platform?token=secreto-de-prueba").status_code == 200


def test_health_es_publico(con_token, monkeypatch):
    class _Manager:
        def ollama_available(self):
            return False

        def ollama_version(self):
            return None

    app_module.api.dependency_overrides[app_module.get_runtime_manager] = _Manager
    try:
        assert con_token.get("/health").status_code == 200
    finally:
        app_module.api.dependency_overrides.clear()


def test_websocket_sin_token_se_cierra(con_token):
    with pytest.raises(WebSocketDisconnect) as exc, con_token.websocket_connect("/chat") as ws:
        ws.receive_json()
    assert exc.value.code == 4401


class _FakeProfile:
    def to_dict(self):
        return {"family": "jetson"}
