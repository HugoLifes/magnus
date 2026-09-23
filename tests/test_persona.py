"""Personalidad de Magnus: identidad, tono y adaptación al tamaño del modelo."""

from __future__ import annotations

import pytest

from core.persona import (
    DEFAULT_PERSONA,
    PERSONAS,
    SMALL_MODEL_B,
    compose,
    get_persona,
    identity_line,
    list_personas,
)


def test_hay_varias_personalidades_y_una_por_omision():
    ids = [p.id for p in PERSONAS]
    assert DEFAULT_PERSONA in ids
    assert len(ids) == len(set(ids)) >= 3
    for p in PERSONAS:
        assert p.name and p.tagline and p.prompt.strip() and p.brief.strip()
        # La versión corta existe para ahorrar contexto: tiene que ser más corta.
        assert len(p.brief) < len(p.prompt)


def test_una_personalidad_desconocida_cae_en_la_de_omision():
    assert get_persona("no-existe").id == DEFAULT_PERSONA
    assert get_persona(None).id == DEFAULT_PERSONA
    assert get_persona("  DIRECTO ").id == "directo"


def test_listado_para_la_app():
    datos = list_personas()
    assert {"id", "name", "tagline"} == set(datos[0])
    assert any(d["id"] == DEFAULT_PERSONA for d in datos)


def test_la_identidad_no_se_hace_pasar_por_otro():
    linea = identity_line("NVIDIA GeForce GTX 1650", "qwen3:4b")
    assert "Magnus" in linea
    assert "GTX 1650" in linea and "qwen3:4b" in linea
    for otro in ("Claude", "ChatGPT", "Gemini"):
        assert otro in linea  # los nombra para negarlos
    assert "No eres" in linea


def test_prompt_completo_en_un_modelo_grande():
    texto = compose("mentor", params_b=14.0, hardware="RTX 4090")
    assert "Eres Magnus" in texto
    assert "error típico" in texto  # el cuerpo largo de la personalidad
    assert "RTX 4090" in texto


def test_prompt_corto_en_un_modelo_pequeno():
    grande = compose("mentor", params_b=14.0, hardware="Jetson Orin Nano")
    chico = compose("mentor", params_b=SMALL_MODEL_B - 1, hardware="Jetson Orin Nano")
    assert len(chico) < len(grande) / 2
    assert "Magnus" in chico and "Jetson Orin Nano" in chico


def test_sin_saber_el_tamano_se_usa_el_prompt_completo():
    assert len(compose("magnus")) > len(compose("magnus", params_b=1.0))


def test_lo_que_pide_el_usuario_va_al_final():
    texto = compose("directo", params_b=8.0, extra="Responde siempre en inglés.")
    assert texto.endswith("Responde siempre en inglés.")


def test_extra_vacio_no_deja_lineas_sueltas():
    assert not compose("magnus", extra="   ").endswith("\n")


@pytest.mark.parametrize("persona", [p.id for p in PERSONAS])
def test_todas_dicen_que_no_inventen(persona):
    texto = compose(persona, params_b=8.0)
    assert "no sabes" in texto.lower() or "inventes" in texto.lower()
