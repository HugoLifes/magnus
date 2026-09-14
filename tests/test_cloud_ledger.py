"""Libro mayor de créditos y precios de Magnus Cloud. SQLite en memoria."""

from __future__ import annotations

import pytest

from cloud.ledger import Ledger, LedgerError, month_ref, normalize_code
from cloud.packs import FREE_MONTHLY_CREDITS, MILLI, PACKS, ModelPrice, tokens_for_credits


@pytest.fixture
def ledger():
    led = Ledger(":memory:")
    yield led
    led.close()


def test_cuenta_y_clave(ledger):
    acc, key = ledger.create_account("Despacho Juárez")
    assert key.startswith("mgk_")
    assert ledger.account_by_key(key) == acc
    assert ledger.account_by_key("mgk_otra") is None


def test_bono_mensual_una_vez_por_mes(ledger):
    acc, _ = ledger.create_account("x")
    septiembre = 1_788_000_000.0  # 2026-08/09
    assert ledger.ensure_monthly_grant(acc.id, septiembre) is True
    assert ledger.ensure_monthly_grant(acc.id, septiembre) is False
    assert ledger.balance_mc(acc.id) == FREE_MONTHLY_CREDITS * MILLI
    assert ledger.ensure_monthly_grant(acc.id, septiembre + 40 * 86400) is True
    assert month_ref(septiembre) != month_ref(septiembre + 40 * 86400)


def test_cobro_idempotente_por_peticion(ledger):
    acc, _ = ledger.create_account("x")
    ledger.ensure_monthly_grant(acc.id)
    assert ledger.debit(acc.id, 1500, "abc", {"modelo": "m"}) is True
    assert ledger.debit(acc.id, 1500, "abc", {"modelo": "m"}) is False
    assert ledger.balance_mc(acc.id) == FREE_MONTHLY_CREDITS * MILLI - 1500
    assert ledger.history(acc.id)[0]["kind"] == "debit"


def test_vales_se_canjean_una_sola_vez(ledger):
    acc, _ = ledger.create_account("x")
    [code] = ledger.create_vouchers("impulso", 1)
    assert code.startswith("MAG-") and len(code) == 18

    # Tolera minúsculas, espacios y confundir O con 0.
    typed = code.lower().replace("-", " ").replace("0", "o")
    assert ledger.redeem(acc.id, typed) == PACKS["impulso"].credits
    with pytest.raises(LedgerError, match="ya se canjeó"):
        ledger.redeem(acc.id, code)
    with pytest.raises(LedgerError, match="no existe"):
        ledger.redeem(acc.id, "MAG-0000-0000-0000")


def test_vales_invalidos(ledger):
    with pytest.raises(LedgerError, match="Paquete desconocido"):
        ledger.create_vouchers("gratis", 1)
    with pytest.raises(LedgerError, match="entre 1 y 1000"):
        ledger.create_vouchers("chispa", 0)


def test_normalizar_codigo():
    assert normalize_code("mag-7k2p-9xqr-ab12") == "MAG7K2P9XQRAB12"
    assert normalize_code("7K2P9XQRAB12") == "MAG7K2P9XQRAB12"
    # Un cuerpo que empieza con MAG no pierde sus letras.
    assert normalize_code("MAG-MAGX-YZ12-3456") == "MAGMAGXYZ123456"


def test_precio_redondea_hacia_arriba():
    price = ModelPrice("qwen3-32b", "Qwen/Qwen3-32B-AWQ", 300, 900)
    assert price.cost_mc(1, 0) == 1           # 0.0003 créditos → 1 milicrédito
    assert price.cost_mc(1_000_000, 1_000_000) == 1_200_000
    assert price.affordable_output_tokens(900 * MILLI, 0) == 1_000_000
    assert price.affordable_output_tokens(10, 1_000_000) == 0


def test_paquetes_regalan_mas_cuanto_mas_grandes():
    ordered = sorted(PACKS.values(), key=lambda p: p.price_usd)
    per_credit = [p.price_usd / p.credits for p in ordered]
    assert per_credit == sorted(per_credit, reverse=True)
    assert sum(p.featured for p in ordered) == 1
    price = ModelPrice("m", "m", 300, 900)
    assert tokens_for_credits(22_000, price) > 40_000_000
