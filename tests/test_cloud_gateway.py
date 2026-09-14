"""Gateway de Magnus Cloud contra un vLLM falso. Sin red ni GPU."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from cloud.gateway import create_app
from cloud.ledger import Ledger
from cloud.packs import FREE_MONTHLY_CREDITS, ModelPrice

ADMIN = "token-operador"
PRICE = ModelPrice("qwen3-32b", "Qwen/Qwen3-32B-AWQ", 300, 900, "Qwen3 32B")


class FakeVllm:
    def __init__(self):
        self.bodies: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        usage = {"prompt_tokens": 1000, "completion_tokens": 2000}
        if body.get("stream"):
            events = [
                {"choices": [{"delta": {"content": "Hola"}}], "model": body["model"]},
                {"choices": [{"delta": {"content": " desde el B200"}}], "model": body["model"]},
                {"choices": [], "usage": usage, "model": body["model"]},
            ]
            sse = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
            return httpx.Response(200, content=sse.encode(),
                                  headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={
            "model": body["model"], "usage": usage,
            "choices": [{"message": {"role": "assistant", "content": "Hola"}}]})


@pytest.fixture
def gw():
    ledger = Ledger(":memory:")
    vllm = FakeVllm()
    app = create_app(ledger, "http://vllm:8000/v1", {PRICE.id: PRICE}, admin_token=ADMIN,
                     transport=httpx.MockTransport(vllm))
    client = TestClient(app)
    key = client.post("/admin/accounts", json={"name": "Clínica Norte"},
                      headers={"x-admin-token": ADMIN}).json()["api_key"]
    yield client, ledger, vllm, {"Authorization": f"Bearer {key}"}
    ledger.close()


def test_paquetes_publicos(gw):
    client, *_ = gw
    body = client.get("/v1/packs").json()
    assert body["free_monthly_credits"] == FREE_MONTHLY_CREDITS
    impulso = next(p for p in body["packs"] if p["id"] == "impulso")
    assert impulso["featured"] and impulso["approx_tokens"] > 0


def test_sin_clave_y_sin_operador(gw):
    client, *_ = gw
    assert client.get("/v1/account").status_code == 401
    r = client.post("/admin/accounts", json={"name": "x"})
    assert r.status_code == 403 and "operador" in r.json()["error"]["message"]


def test_bono_gratis_al_primer_uso(gw):
    client, _, _, auth = gw
    acc = client.get("/v1/account", headers=auth).json()
    assert acc["balance_credits"] == FREE_MONTHLY_CREDITS
    assert acc["history"][0]["kind"] == "grant"


def test_chat_sin_streaming_cobra_lo_reportado(gw):
    client, _, vllm, auth = gw
    r = client.post("/v1/chat/completions", headers=auth, json={
        "model": "qwen3-32b", "messages": [{"role": "user", "content": "hola"}]})
    assert r.status_code == 200
    assert r.json()["model"] == "qwen3-32b"                  # nombre público de vuelta
    assert vllm.bodies[0]["model"] == "Qwen/Qwen3-32B-AWQ"   # nombre interno hacia vLLM
    # 1000×300 + 2000×900 por millón = 2.1 créditos
    assert client.get("/v1/account", headers=auth).json()["balance_credits"] == pytest.approx(97.9)


def test_chat_con_streaming(gw):
    client, _, vllm, auth = gw
    with client.stream("POST", "/v1/chat/completions", headers=auth, json={
            "model": "qwen3-32b", "stream": True,
            "messages": [{"role": "user", "content": "hola"}]}) as r:
        text = "".join(r.iter_text())
    assert "desde el B200" in text and "Qwen/Qwen3-32B-AWQ" not in text
    assert vllm.bodies[0]["stream_options"] == {"include_usage": True}
    assert client.get("/v1/account", headers=auth).json()["balance_credits"] == pytest.approx(97.9)


def test_sin_saldo_402(gw):
    client, _, vllm, auth = gw
    acc_id = client.get("/v1/account", headers=auth).json()["account"]["id"]
    client.post(f"/admin/accounts/{acc_id}/grant", headers={"x-admin-token": ADMIN},
                json={"credits": -FREE_MONTHLY_CREDITS, "ref": "prueba"})
    r = client.post("/v1/chat/completions", headers=auth, json={
        "model": "qwen3-32b", "messages": [{"role": "user", "content": "hola"}]})
    assert r.status_code == 402 and "Saldo insuficiente" in r.json()["error"]["message"]
    assert vllm.bodies == []


def test_recorta_max_tokens_al_saldo(gw):
    client, _, vllm, auth = gw
    acc_id = client.get("/v1/account", headers=auth).json()["account"]["id"]
    client.post(f"/admin/accounts/{acc_id}/grant", headers={"x-admin-token": ADMIN},
                json={"credits": -99, "ref": "dejar-1"})
    client.post("/v1/chat/completions", headers=auth, json={
        "model": "qwen3-32b", "max_tokens": 8000,
        "messages": [{"role": "user", "content": "hola"}]})
    # 1 crédito menos la entrada estimada (1 milicrédito) paga 1110 tokens a 900/millón.
    assert vllm.bodies[0]["max_tokens"] == 1110


def test_modelo_desconocido(gw):
    client, _, _, auth = gw
    r = client.post("/v1/chat/completions", headers=auth,
                    json={"model": "gpt-9", "messages": []})
    assert r.status_code == 404 and "qwen3-32b" in r.json()["error"]["message"]


def test_canjear_vale(gw):
    client, _, _, auth = gw
    [code] = client.post("/admin/vouchers", headers={"x-admin-token": ADMIN},
                         json={"pack_id": "chispa", "count": 1}).json()["codes"]
    ok = client.post("/v1/redeem", headers=auth, json={"code": code}).json()
    assert ok["added_credits"] == 5000 and ok["balance_credits"] == 5100
    again = client.post("/v1/redeem", headers=auth, json={"code": code})
    assert again.status_code == 400 and "ya se canjeó" in again.json()["error"]["message"]


def test_modelos_con_precio(gw):
    client, _, _, auth = gw
    data = client.get("/v1/models", headers=auth).json()["data"]
    assert data[0]["id"] == "qwen3-32b"
    assert data[0]["pricing"]["output_credits_per_mtok"] == 900
    assert "upstream_model" not in data[0]["pricing"]
