"""Gateway de Magnus Cloud: API compatible con OpenAI con saldo de créditos.

Se pone delante de un servidor vLLM en cualquier equipo NVIDIA. Por cada
petición:

1. identifica la cuenta por su clave (`Authorization: Bearer mgk_...`);
2. aplica el bono gratuito del mes si toca;
3. se niega con 402 si no hay saldo, y recorta `max_tokens` a lo que el saldo paga
   — así una petición nunca deja la cuenta en negativo por mucho;
4. reenvía a vLLM pidiendo el conteo de tokens (`include_usage`);
5. cobra con los tokens que reporta vLLM, redondeando hacia arriba.

Si el cliente corta a mitad del streaming se cobra lo generado hasta ahí.

Arranque:
    MAGNUS_GATEWAY_CONFIG=deploy/cloud/models.json \\
    MAGNUS_GATEWAY_DB=/data/ledger.db MAGNUS_GATEWAY_ADMIN_TOKEN=... \\
    uvicorn cloud.gateway:app_from_env --factory --host 0.0.0.0 --port 8430
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from cloud.ledger import Account, Ledger, LedgerError
from cloud.packs import (
    FREE_MONTHLY_CREDITS,
    PACKS,
    USD_PER_CREDIT,
    ModelPrice,
    credits_from_mc,
    tokens_for_credits,
)

# Tokens de salida por defecto si el cliente no pone max_tokens.
_DEFAULT_MAX_TOKENS = 2048
# Estimación grosera de tokens por carácter para reservar saldo antes de llamar.
_CHARS_PER_TOKEN = 4


def _error(status: int, message: str) -> JSONResponse:
    # Misma forma que la API de OpenAI: los clientes ya saben leerla.
    return JSONResponse(status_code=status, content={"error": {"message": message}})


def load_models(config_path: Path) -> tuple[str, dict[str, ModelPrice]]:
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    models = {m["id"]: ModelPrice(**m) for m in data["models"]}
    return data["upstream"], models


class RedeemBody(BaseModel):
    code: str


class AccountBody(BaseModel):
    name: str


class VoucherBody(BaseModel):
    pack_id: str
    count: int = 1


class GrantBody(BaseModel):
    credits: int
    ref: str
    reason: str = "ajuste manual"


def create_app(
    ledger: Ledger,
    upstream_url: str,
    models: dict[str, ModelPrice],
    admin_token: str | None = None,
    transport: httpx.BaseTransport | None = None,
    upstream_key: str | None = None,
) -> FastAPI:
    app = FastAPI(title="Magnus Cloud gateway", version="0.1.0")
    upstream_url = upstream_url.rstrip("/")
    headers = {"Authorization": f"Bearer {upstream_key}"} if upstream_key else {}
    http = httpx.Client(transport=transport, headers=headers,
                        timeout=httpx.Timeout(10.0, read=600.0))

    def account_for(authorization: str | None) -> Account:
        key = (authorization or "")[7:].strip() if (authorization or "").lower().startswith(
            "bearer ") else ""
        account = ledger.account_by_key(key) if key else None
        if account is None:
            raise HTTPException(status_code=401, detail="Clave de Magnus Cloud no válida.")
        ledger.ensure_monthly_grant(account.id)
        return account

    def require_admin(token: str | None) -> None:
        if not admin_token or not token or not secrets.compare_digest(token, admin_token):
            raise HTTPException(status_code=403, detail="Solo para el operador.")

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return _error(exc.status_code, str(exc.detail))

    # --- públicas ---------------------------------------------------------

    @app.get("/v1/packs")
    def packs() -> dict:
        reference = next(iter(models.values()), None)
        return {
            "usd_per_credit": USD_PER_CREDIT,
            "free_monthly_credits": FREE_MONTHLY_CREDITS,
            "packs": [p.to_dict() | {
                "approx_tokens": tokens_for_credits(p.credits, reference) if reference else None,
                "reference_model": reference.id if reference else None,
            } for p in PACKS.values()],
        }

    # --- con clave --------------------------------------------------------

    @app.get("/v1/models")
    def list_models(authorization: str | None = Header(default=None)) -> dict:
        account_for(authorization)
        return {"object": "list",
                "data": [{"id": m.id, "object": "model", "owned_by": "magnus-cloud",
                          "pricing": m.to_dict()} for m in models.values()]}

    @app.get("/v1/account")
    def account(authorization: str | None = Header(default=None)) -> dict:
        acc = account_for(authorization)
        balance = ledger.balance_mc(acc.id)
        return {
            "account": acc.to_dict(),
            "balance_credits": credits_from_mc(balance),
            "balance_usd": round(credits_from_mc(balance) * USD_PER_CREDIT, 4),
            "free_monthly_credits": FREE_MONTHLY_CREDITS,
            "history": ledger.history(acc.id, limit=30),
        }

    @app.post("/v1/redeem")
    def redeem(body: RedeemBody, authorization: str | None = Header(default=None)) -> dict:
        acc = account_for(authorization)
        try:
            added = ledger.redeem(acc.id, body.code)
        except LedgerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"added_credits": added,
                "balance_credits": credits_from_mc(ledger.balance_mc(acc.id))}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request,
                               authorization: str | None = Header(default=None)):
        acc = account_for(authorization)
        body = await request.json()
        price = models.get(body.get("model", ""))
        if price is None:
            return _error(404, f"El modelo '{body.get('model')}' no está en Magnus Cloud. "
                               f"Disponibles: {', '.join(models)}")
        balance = ledger.balance_mc(acc.id)
        if balance <= 0:
            return _error(402, "Saldo insuficiente en Magnus Cloud. Recarga un paquete de "
                               "créditos o usa un modelo local.")
        prompt_chars = sum(len(str(m.get("content", ""))) for m in body.get("messages", []))
        affordable = price.affordable_output_tokens(balance, prompt_chars // _CHARS_PER_TOKEN)
        if affordable <= 0:
            return _error(402, "El saldo no alcanza ni para leer este mensaje. Recarga créditos.")
        wanted = body.get("max_tokens") or _DEFAULT_MAX_TOKENS
        body["max_tokens"] = min(int(wanted), affordable)
        public_model = body["model"]
        body["model"] = price.upstream_model
        request_id = uuid.uuid4().hex

        def charge(usage: dict, generated_chars: int, partial: bool) -> None:
            tokens_in = usage.get("prompt_tokens") or prompt_chars // _CHARS_PER_TOKEN
            tokens_out = usage.get("completion_tokens")
            if tokens_out is None:
                tokens_out = generated_chars // _CHARS_PER_TOKEN
            cost = price.cost_mc(tokens_in, tokens_out)
            if cost > 0:
                ledger.debit(acc.id, cost, request_id, {
                    "modelo": public_model, "tokens_in": tokens_in, "tokens_out": tokens_out,
                    "estimado": not usage, "cortado": partial})

        if not body.get("stream"):
            try:
                r = http.post(f"{upstream_url}/chat/completions", json=body)
            except httpx.HTTPError:
                return _error(503, "El servidor de modelos de Magnus Cloud no responde.")
            if r.status_code >= 400:
                return JSONResponse(status_code=r.status_code, content=r.json())
            data = r.json()
            text = "".join((c.get("message") or {}).get("content") or ""
                           for c in data.get("choices", []))
            charge(data.get("usage") or {}, len(text), partial=False)
            data["model"] = public_model
            return data

        body["stream_options"] = {"include_usage": True}

        def relay() -> Iterator[bytes]:
            usage: dict = {}
            generated = 0
            finished = False
            try:
                with http.stream("POST", f"{upstream_url}/chat/completions", json=body) as r:
                    if r.status_code >= 400:
                        r.read()
                        yield (f"data: {json.dumps({'error': {'message': r.text}})}\n\n").encode()
                        return
                    for line in r.iter_lines():
                        if line.startswith("data:") and line[5:].strip() != "[DONE]":
                            chunk = json.loads(line[5:])
                            usage = chunk.get("usage") or usage
                            for choice in chunk.get("choices", []):
                                generated += len((choice.get("delta") or {}).get("content") or "")
                            chunk["model"] = public_model
                            line = f"data: {json.dumps(chunk, ensure_ascii=False)}"
                        yield (line + "\n\n").encode() if line else b""
                finished = True
            except httpx.HTTPError:
                cut = {"error": {"message": "Se cortó la conexión con el servidor de modelos."}}
                yield f"data: {json.dumps(cut, ensure_ascii=False)}\n\n".encode()
            finally:
                charge(usage, generated, partial=not finished)

        return StreamingResponse(relay(), media_type="text/event-stream")

    # --- operador ---------------------------------------------------------

    @app.post("/admin/accounts")
    def admin_account(body: AccountBody, x_admin_token: str | None = Header(default=None)):
        require_admin(x_admin_token)
        acc, key = ledger.create_account(body.name)
        return {"account": acc.to_dict(), "api_key": key,
                "aviso": "Guarda la clave: no se puede volver a mostrar."}

    @app.post("/admin/vouchers")
    def admin_vouchers(body: VoucherBody, x_admin_token: str | None = Header(default=None)):
        require_admin(x_admin_token)
        try:
            return {"pack_id": body.pack_id, "codes": ledger.create_vouchers(body.pack_id,
                                                                             body.count)}
        except LedgerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/admin/accounts/{account_id}/grant")
    def admin_grant(account_id: str, body: GrantBody,
                    x_admin_token: str | None = Header(default=None)):
        require_admin(x_admin_token)
        if ledger.get_account(account_id) is None:
            raise HTTPException(status_code=404, detail="Cuenta inexistente.")
        applied = ledger.add(account_id, "adjust", body.credits * 1000, body.ref,
                             {"motivo": body.reason})
        return {"applied": applied,
                "balance_credits": credits_from_mc(ledger.balance_mc(account_id))}

    return app


def app_from_env() -> FastAPI:
    """Fábrica para uvicorn --factory, configurada por variables de entorno."""
    upstream, models = load_models(Path(os.environ["MAGNUS_GATEWAY_CONFIG"]))
    ledger = Ledger(os.environ.get("MAGNUS_GATEWAY_DB", "ledger.db"))
    return create_app(ledger, os.environ.get("MAGNUS_GATEWAY_UPSTREAM", upstream), models,
                      admin_token=os.environ.get("MAGNUS_GATEWAY_ADMIN_TOKEN"),
                      upstream_key=os.environ.get("MAGNUS_GATEWAY_UPSTREAM_KEY"))
