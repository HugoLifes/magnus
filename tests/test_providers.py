"""Proveedores: registro, validaciones y cliente compatible con OpenAI. Sin red."""

from __future__ import annotations

import json

import httpx
import pytest

from core.providers import (
    PRESETS,
    OpenAICompatClient,
    Provider,
    ProviderError,
    ProviderKind,
    ProviderRegistry,
)
from core.secrets import SecretStore


@pytest.fixture
def registry(tmp_path):
    return ProviderRegistry(tmp_path, SecretStore(tmp_path, use_keyring=False))


def _nvidia(**kw) -> Provider:
    base = {"id": "nvidia", "kind": ProviderKind.NVIDIA, "name": "NVIDIA API",
            "base_url": PRESETS[ProviderKind.NVIDIA].base_url}
    return Provider(**(base | kw))


# --- registro --------------------------------------------------------------


def test_guarda_con_clave_y_no_la_escribe_en_el_json(registry, tmp_path):
    registry.save(_nvidia(), api_key="nvapi-secreta")
    assert registry.has_key("nvidia")
    assert "nvapi-secreta" not in (tmp_path / "providers.json").read_text()
    [p] = registry.list()
    assert p.to_dict(registry.has_key(p.id))["has_key"] is True
    assert "api_key" not in p.to_dict()


def test_proveedor_con_clave_obligatoria_sin_clave(registry):
    with pytest.raises(ProviderError, match="necesita una clave"):
        registry.save(_nvidia())


def test_vllm_en_la_red_sin_clave(registry):
    p = registry.save(Provider("spark", ProviderKind.VLLM, "DGX Spark",
                               "http://192.168.1.40:8000/v1/"))
    assert p.base_url == "http://192.168.1.40:8000/v1"
    assert p.location == "lan"


def test_http_fuera_de_la_red_se_rechaza(registry):
    with pytest.raises(ProviderError, match="https"):
        registry.save(Provider("x", ProviderKind.VLLM, "x", "http://203.0.113.9:8000/v1"))


def test_ids_invalidos_y_reservados(registry):
    with pytest.raises(ProviderError, match="identificador"):
        registry.save(Provider("Con Espacios", ProviderKind.VLLM, "x", "http://127.0.0.1/v1"))
    with pytest.raises(ProviderError, match="reservado"):
        registry.save(Provider("local", ProviderKind.VLLM, "x", "http://127.0.0.1/v1"))


def test_borrar_quita_tambien_la_clave(registry):
    registry.save(_nvidia(), api_key="k")
    assert registry.delete("nvidia") is True
    assert registry.list() == [] and not registry.has_key("nvidia")
    assert registry.delete("nvidia") is False


def test_actualizar_sin_repetir_clave(registry):
    registry.save(_nvidia(), api_key="k")
    registry.save(_nvidia(default_model="meta/llama-3.3-70b-instruct"))
    assert registry.get("nvidia").default_model == "meta/llama-3.3-70b-instruct"
    assert registry.has_key("nvidia")


def test_ubicacion_y_coste():
    assert _nvidia().location == "cloud"
    p = Provider("mc", ProviderKind.MAGNUS_CLOUD, "Magnus Cloud", "https://x.example/v1",
                 input_usd_per_mtok=0.2, output_usd_per_mtok=0.6)
    assert p.cost_usd(1_000_000, 500_000) == pytest.approx(0.5)
    assert _nvidia().cost_usd(10, 10) is None


# --- cliente ---------------------------------------------------------------


def _sse(*events: dict) -> bytes:
    lines = [f"data: {json.dumps(e)}\n\n" for e in events] + ["data: [DONE]\n\n"]
    return "".join(lines).encode()


def _client(handler) -> OpenAICompatClient:
    return OpenAICompatClient("https://api.example/v1", "clave", "NVIDIA API",
                              transport=httpx.MockTransport(handler))


def test_stream_con_forma_de_ollama():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, content=_sse(
            {"choices": [{"delta": {"reasoning_content": "Pienso"}}]},
            {"choices": [{"delta": {"content": "Hola"}}]},
            {"choices": [{"delta": {"content": " mundo"}}]},
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}},
        ), headers={"content-type": "text/event-stream"})

    chunks = list(_client(handler).stream_chat(
        "meta/llama-3.1-8b-instruct", [{"role": "user", "content": "hola"}],
        options={"temperature": 0.2, "num_predict": 64}, think=False))

    assert seen["auth"] == "Bearer clave"
    assert seen["body"]["stream_options"] == {"include_usage": True}
    assert seen["body"]["max_tokens"] == 64 and seen["body"]["temperature"] == 0.2
    assert seen["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert chunks[0]["message"]["thinking"] == "Pienso"
    assert "".join(c["message"]["content"] for c in chunks) == "Hola mundo"
    final = chunks[-1]
    assert final["done"] is True
    assert final["prompt_eval_count"] == 12 and final["eval_count"] == 3


@pytest.mark.parametrize(("status", "texto"), [
    (401, "no es válida"),
    (402, "Saldo insuficiente"),
    (429, "limitó"),
    (404, "no existe"),
])
def test_errores_legibles(status, texto):
    client = _client(lambda r: httpx.Response(status, json={"error": {"message": "x"}}))
    with pytest.raises(ProviderError, match=texto):
        list(client.stream_chat("m", []))


def test_lista_modelos():
    client = _client(lambda r: httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]}))
    assert client.list_models() == ["a", "b"]


def test_sin_conexion():
    def handler(request):
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(ProviderError, match="No se puede conectar"):
        _client(handler).list_models()


def test_tamano_por_nombre():
    client = OpenAICompatClient("http://127.0.0.1/v1", None)
    assert client.parameter_size_b("meta/llama-3.3-70b-instruct") == 70
    assert client.parameter_size_b("qwen3-1.7b") == 1.7
    assert client.parameter_size_b("gpt-oss") is None


def test_cuenta_y_canje_en_magnus_cloud():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json={"balance_credits": 97.9})
        if request.url.path.endswith("/redeem"):
            return httpx.Response(400, json={"error": {"message": "Ese código ya se canjeó."}})
        return httpx.Response(404)

    client = _client(handler)
    assert client.account()["balance_credits"] == 97.9
    with pytest.raises(ProviderError, match="^Ese código ya se canjeó.$"):
        client.redeem("MAG-1")
