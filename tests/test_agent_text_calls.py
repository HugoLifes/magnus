"""Rescatar llamadas a herramientas que el modelo escribe como texto.

Medido en la PC de desarrollo: `qwen2.5-coder:7b` responde el JSON de la llamada
en vez de emitirla por el protocolo, porque su plantilla no trae `tool_calls`.
Sin este rescate, el agente se queda sin usar sus herramientas.
"""

from __future__ import annotations

from core.agent import _calls_in_text


def test_se_rescata_una_llamada_escrita_como_texto():
    texto = 'Claro: {"name": "calcular", "arguments": {"expresion": "1250*1.16"}}'
    calls = _calls_in_text(texto, ("calcular", "fecha_hora"))
    assert calls == [{"function": {"name": "calcular",
                                   "arguments": {"expresion": "1250*1.16"}}}]


def test_solo_se_rescatan_herramientas_del_agente():
    """Que el texto nombre una herramienta no la habilita: manda el permiso del agente."""
    texto = '{"name": "borrar_todo", "arguments": {"ruta": "/"}}'
    assert _calls_in_text(texto, ("calcular",)) == []


def test_varias_llamadas_en_el_mismo_texto():
    texto = ('{"name": "calcular", "arguments": {"expresion": "2+2"}} y luego '
             '{"name": "fecha_hora", "arguments": {}}')
    nombres = [c["function"]["name"] for c in _calls_in_text(texto, ("calcular", "fecha_hora"))]
    assert nombres == ["calcular", "fecha_hora"]


def test_json_roto_se_ignora():
    texto = '{"name": "calcular", "arguments": {"expresion": }}'
    assert _calls_in_text(texto, ("calcular",)) == []


def test_una_respuesta_normal_no_inventa_llamadas():
    assert _calls_in_text("La cuantización reduce la precisión de los pesos.", ("calcular",)) == []
    assert _calls_in_text("", ("calcular",)) == []
