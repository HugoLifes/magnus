"""Configuración y carpeta de datos. Corren SIN GPU."""

from __future__ import annotations

import pytest

from core.config import Settings, data_dir, load_settings, save_settings


def test_magnus_home_manda(monkeypatch, tmp_path):
    monkeypatch.setenv("MAGNUS_HOME", str(tmp_path))
    assert data_dir() == tmp_path


def test_valores_por_defecto(tmp_path, monkeypatch):
    for var in ("MAGNUS_OLLAMA_URL", "MAGNUS_PORT", "MAGNUS_API_TOKEN", "MAGNUS_HOST"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings(tmp_path)
    assert s == Settings()
    assert s.host == "127.0.0.1"


def test_guardar_y_releer(tmp_path, monkeypatch):
    monkeypatch.delenv("MAGNUS_PORT", raising=False)
    s = save_settings({"port": "9000", "electricity_usd_per_kwh": 0.08,
                       "hardware_cost_usd": 249}, tmp_path)
    assert s.port == 9000
    assert s.electricity_usd_per_kwh == 0.08
    assert s.hardware_cost_usd == 249.0
    assert load_settings(tmp_path).port == 9000


def test_entorno_gana_al_archivo(tmp_path, monkeypatch):
    save_settings({"ollama_url": "http://archivo:11434"}, tmp_path)
    monkeypatch.setenv("MAGNUS_OLLAMA_URL", "http://entorno:11434")
    assert load_settings(tmp_path).ollama_url == "http://entorno:11434"


def test_ajuste_desconocido(tmp_path):
    with pytest.raises(ValueError, match="desconocidos"):
        save_settings({"color_favorito": "verde"}, tmp_path)


def test_archivo_corrupto_no_rompe(tmp_path, monkeypatch):
    monkeypatch.delenv("MAGNUS_PORT", raising=False)
    (tmp_path / "config.json").write_text("{no es json")
    assert load_settings(tmp_path).port == 8420


def test_token_no_se_expone():
    assert Settings(api_token="secreto").to_dict()["api_token"] == "***"
