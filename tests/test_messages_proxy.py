"""Proxy de la API de mensajes: elección de modelo, guarda de memoria y medición."""

from __future__ import annotations

import json

import httpx
import pytest

from core.config import Settings
from core.messages import MessagesProxy, ProxyError
from core.platform import detect_platform
from core.store import Store


class FakeManager:
    """RuntimeManager de mentira: dice qué hay descargado y anota qué se cargó."""

    def __init__(self, available: list[str]) -> None:
        self.available = available
        self.loaded: list[str] = []
        self.fail: str | None = None

    def list_available(self) -> list[str]:
        return list(self.available)

    def ensure_loaded(self, model_id: str):
        from core.runtime_manager import RuntimeManagerError

        if self.fail:
            raise RuntimeManagerError(self.fail)
        self.loaded.append(model_id)


def _respuesta(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("POST", "http://x/v1/messages"))


def _proxy(tmp_path, available, *, post=None, stream_post=None):
    return MessagesProxy(
        manager=FakeManager(available),
        store=Store(tmp_path / "magnus.db"),
        settings=Settings(),
        platform=detect_platform([]),
        post=post,
        stream_post=stream_post,
    )


# --- Elegir el modelo -------------------------------------------------------


def test_un_modelo_de_la_nube_se_traduce_al_mejor_local(tmp_path):
    proxy = _proxy(tmp_path, ["qwen2.5:0.5b", "qwen2.5-coder:7b"])
    assert proxy.resolve_model("claude-sonnet-4-5") == "qwen2.5-coder:7b"


def test_respeta_el_modelo_si_esta_descargado(tmp_path):
    proxy = _proxy(tmp_path, ["qwen2.5:0.5b", "qwen2.5-coder:7b"])
    assert proxy.resolve_model("qwen2.5:0.5b") == "qwen2.5:0.5b"


def test_magnus_auto_deja_elegir_a_magnus(tmp_path):
    """Es lo que manda `magnus claude`: que elija el equipo, no el cliente."""
    proxy = _proxy(tmp_path, ["qwen2.5:0.5b", "qwen2.5-coder:7b"])
    for pedido in ("magnus-auto", "auto", "", "MAGNUS-AUTO"):
        assert proxy.resolve_model(pedido) == "qwen2.5-coder:7b", pedido


def test_modelo_local_inexistente_lo_dice(tmp_path):
    proxy = _proxy(tmp_path, ["qwen2.5:0.5b"])
    with pytest.raises(ProxyError, match="no está descargado"):
        proxy.resolve_model("llama3.2:70b")


def test_sin_modelos_descargados_explica_como_descargar(tmp_path):
    proxy = _proxy(tmp_path, [])
    with pytest.raises(ProxyError, match="magnus fetch"):
        proxy.resolve_model("claude-sonnet-4-5")


# --- Turno sin streaming ----------------------------------------------------


def test_turno_completo_mide_y_registra(tmp_path):
    llamadas = {}

    def post(url, json=None, timeout=None):
        llamadas["body"] = json
        return _respuesta({
            "type": "message",
            "content": [{"type": "text", "text": "hola"}],
            "usage": {"input_tokens": 12, "output_tokens": 30},
        })

    proxy = _proxy(tmp_path, ["qwen2.5-coder:7b"], post=post)
    turno = proxy.complete({"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hola"}]})

    # El modelo viaja traducido y sin streaming.
    assert llamadas["body"]["model"] == "qwen2.5-coder:7b"
    assert llamadas["body"]["stream"] is False
    assert turno.metrics.tokens_in == 12
    assert turno.metrics.tokens_out == 30
    assert turno.metrics.cloud_cost_usd > 0  # hay ahorro que enseñar

    # Y el turno suma al medidor aunque no haya conversación.
    resumen = Store(tmp_path / "magnus.db").usage_summary()
    assert resumen["turns"] == 1
    assert resumen["tokens_out"] == 30


def test_error_del_runtime_se_explica(tmp_path):
    def post(url, json=None, timeout=None):
        return _respuesta({"error": {"message": "model not found"}}, status=404)

    proxy = _proxy(tmp_path, ["qwen2.5-coder:7b"], post=post)
    with pytest.raises(ProxyError, match="404"):
        proxy.complete({"model": "claude", "messages": [{"role": "user", "content": "x"}]})


def test_peticion_sin_mensajes(tmp_path):
    proxy = _proxy(tmp_path, ["qwen2.5-coder:7b"])
    with pytest.raises(ProxyError, match="mensajes"):
        proxy.complete({"model": "claude"})


def test_la_guarda_de_memoria_manda(tmp_path):
    proxy = _proxy(tmp_path, ["qwen2.5-coder:7b"])
    proxy._manager.fail = "No cabe en la memoria de este equipo."
    with pytest.raises(ProxyError, match="No cabe"):
        proxy.complete({"model": "claude", "messages": [{"role": "user", "content": "x"}]})


# --- Turno con streaming ----------------------------------------------------


class FakeStream:
    """Devuelve eventos SSE como los de Anthropic."""

    def __init__(self, eventos: list[dict]) -> None:
        self._eventos = eventos

    def __call__(self, url, body):
        self.body = body
        return self

    def __enter__(self):
        return iter([f"data: {json.dumps(e)}" for e in self._eventos])

    def __exit__(self, *exc):
        return None


def test_streaming_reenvia_tal_cual_y_mide(tmp_path):
    stream = FakeStream([
        {"type": "message_start", "message": {"usage": {"input_tokens": 7}}},
        {"type": "content_block_delta", "delta": {"text": "ho"}},
        {"type": "content_block_delta", "delta": {"text": "la"}},
        {"type": "message_delta", "usage": {"output_tokens": 21}},
        {"type": "message_stop"},
    ])
    proxy = _proxy(tmp_path, ["qwen2.5-coder:7b"], stream_post=stream)

    salida = b"".join(proxy.stream({
        "model": "claude-sonnet-4-5",
        "stream": True,
        "messages": [{"role": "user", "content": "hola"}],
    }))

    # Lo que sale es exactamente lo que entró, evento por evento.
    assert salida.count(b"data: ") == 5
    assert b"message_stop" in salida
    assert stream.body["model"] == "qwen2.5-coder:7b"

    resumen = Store(tmp_path / "magnus.db").usage_summary()
    assert resumen["turns"] == 1
    assert resumen["tokens_in"] == 7
    assert resumen["tokens_out"] == 21


def test_streaming_con_error_del_runtime(tmp_path):
    stream = FakeStream([{"type": "error", "error": {"message": "se acabó la memoria"}}])
    proxy = _proxy(tmp_path, ["qwen2.5-coder:7b"], stream_post=stream)
    with pytest.raises(ProxyError, match="se acabó la memoria"):
        list(proxy.stream({"model": "claude", "stream": True,
                           "messages": [{"role": "user", "content": "x"}]}))
