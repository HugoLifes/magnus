"""Tests del downloader HF. Corren SIN GPU y SIN red (usan monkeypatch)."""

from core.downloader import download_model, hf_cli_available


def test_dry_run_devuelve_comando_sin_ejecutar(tmp_path):
    res = download_model(
        "meta-llama/Llama-3.1-8B",
        models_dir=tmp_path,
        dry_run=True,
    )
    assert res.ok
    assert "Llama-3.1-8B" in res.message
    assert "download" in res.message


def test_dry_run_con_include(tmp_path):
    res = download_model(
        "bartowski/Qwen2.5-32B-Instruct-GGUF",
        models_dir=tmp_path,
        allow_patterns=["*Q4_K_M*.gguf"],
        dry_run=True,
    )
    assert res.ok
    assert "--include" in res.message
    assert "Q4_K_M" in res.message


def test_dry_run_con_revision(tmp_path):
    res = download_model(
        "meta-llama/Llama-3.1-8B",
        models_dir=tmp_path,
        revision="main",
        dry_run=True,
    )
    assert "--revision" in res.message
    assert "main" in res.message


def test_sin_cli_falla_con_mensaje(monkeypatch, tmp_path):
    monkeypatch.setattr("core.downloader.hf_cli_available", lambda: None)
    res = download_model("some/model", models_dir=tmp_path)
    assert not res.ok
    assert "huggingface_hub" in res.message.lower() or "CLI" in res.message


def test_dest_path_usa_nombre_de_repo(tmp_path):
    res = download_model("org/modelo", models_dir=tmp_path, dry_run=True)
    assert "org__modelo" in res.dest


def test_hf_cli_available_devuelve_none_o_string(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    assert hf_cli_available() is None
