"""Licencias: firma, verificación sin internet, vencimiento y gracia."""

from __future__ import annotations

import time

import pytest

from core.license import (
    COMMUNITY,
    GRACE_DAYS,
    License,
    LicenseError,
    LicenseStore,
    generate_keypair,
    plan_allows,
    public_key_hex,
    sign_license,
    upgrade_message,
    verify_license,
)

DIA = 86400


@pytest.fixture
def par():
    return generate_keypair()


def _licencia(par, **campos) -> str:
    private, _ = par
    payload = {
        "id": "MAG-0001",
        "plan": "pro",
        "holder": "Hugo",
        "issued": time.time(),
        "expires": time.time() + 30 * DIA,
        "seats": 1,
    }
    payload.update(campos)
    return sign_license(payload, private)


def test_firma_y_verificacion_ida_y_vuelta(par):
    _, public = par
    lic = verify_license(_licencia(par), public_key=public)
    assert lic.plan == "pro"
    assert lic.holder == "Hugo"
    assert lic.status() == "activa"


def test_firma_de_otra_clave_no_pasa(par):
    otro_privado, _ = generate_keypair()
    _, public = par
    texto = sign_license({"id": "MAG-2", "plan": "pro", "issued": 0}, otro_privado)
    with pytest.raises(LicenseError, match="firma"):
        verify_license(texto, public_key=public)


def test_contenido_alterado_no_pasa(par):
    _, public = par
    texto = _licencia(par, plan="pro")
    prefijo, cuerpo, firma = texto.split(".")
    # Cambiar un carácter del contenido invalida la firma.
    alterado = f"{prefijo}.{cuerpo[:-2]}XY.{firma}"
    with pytest.raises(LicenseError):
        verify_license(alterado, public_key=public)


@pytest.mark.parametrize("texto", ["", "hola", "MAGNUS1.solo-dos-partes", "OTRO1.a.b"])
def test_textos_invalidos(texto, par):
    _, public = par
    with pytest.raises(LicenseError):
        verify_license(texto, public_key=public)


def test_plan_desconocido(par):
    _, public = par
    with pytest.raises(LicenseError, match="plan desconocido"):
        verify_license(_licencia(par, plan="ultra"), public_key=public)


def test_vencimiento_y_gracia():
    vence = 1_000_000.0
    lic = License(id="x", plan="pro", holder="", issued=0.0, expires=vence)
    assert lic.status(vence - DIA) == "activa"
    assert lic.status(vence + DIA) == "en gracia"
    assert lic.status(vence + (GRACE_DAYS + 1) * DIA) == "vencida"
    # Vencida del todo: el plan efectivo cae a community, no se queda en pro.
    assert lic.effective_plan(vence + DIA) == "pro"
    assert lic.effective_plan(vence + (GRACE_DAYS + 1) * DIA) == "community"


def test_sin_vencimiento_es_perpetua():
    lic = License(id="x", plan="pro", holder="", issued=0.0, expires=None)
    assert lic.status(time.time() + 10 * 365 * DIA) == "activa"
    assert lic.days_left() is None


def test_orden_de_planes():
    assert plan_allows("team", "pro")
    assert plan_allows("pro", "pro")
    assert not plan_allows("community", "pro")
    with pytest.raises(LicenseError):
        plan_allows("inventado", "pro")


def test_clave_publica_desde_el_entorno(monkeypatch, par):
    _, public = par
    monkeypatch.setenv("MAGNUS_LICENSE_PUBKEY", public)
    assert public_key_hex() == public
    # Sin pasar la clave a mano, usa la del entorno.
    assert verify_license(_licencia(par)).plan == "pro"


def test_guardar_y_leer(tmp_path, monkeypatch, par):
    _, public = par
    monkeypatch.setenv("MAGNUS_LICENSE_PUBKEY", public)
    store = LicenseStore(tmp_path)

    assert store.current() == COMMUNITY

    lic = store.activate(_licencia(par))
    assert lic.plan == "pro"
    assert store.current().plan == "pro"
    assert store.path.exists()

    store.deactivate()
    assert store.current() == COMMUNITY


def test_no_se_activa_una_vencida(tmp_path, monkeypatch, par):
    _, public = par
    monkeypatch.setenv("MAGNUS_LICENSE_PUBKEY", public)
    vieja = _licencia(par, expires=time.time() - (GRACE_DAYS + 2) * DIA)
    with pytest.raises(LicenseError, match="venció"):
        LicenseStore(tmp_path).activate(vieja)


def test_archivo_corrupto_cae_a_community(tmp_path, monkeypatch, par):
    _, public = par
    monkeypatch.setenv("MAGNUS_LICENSE_PUBKEY", public)
    store = LicenseStore(tmp_path)
    store.path.write_text("MAGNUS1.basura.basura", encoding="utf-8")
    assert store.current() == COMMUNITY


def test_mensaje_de_mejora_menciona_el_plan():
    assert "Pro" in upgrade_message("pro")
    assert "Team" in upgrade_message("team")
