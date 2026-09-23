"""SecretStore con respaldo en archivo. No toca el llavero real del sistema."""

from __future__ import annotations

import json

from core.secrets import SecretStore


def test_guarda_lee_y_borra(tmp_path):
    store = SecretStore(tmp_path, use_keyring=False)
    assert store.backend == "archivo local"
    assert store.get("provider:nvidia") is None

    store.set("provider:nvidia", "nvapi-abc")
    assert store.get("provider:nvidia") == "nvapi-abc"

    store.set("provider:nvidia", "nvapi-nueva")
    assert store.get("provider:nvidia") == "nvapi-nueva"

    store.delete("provider:nvidia")
    assert store.get("provider:nvidia") is None


def test_no_mezcla_claves(tmp_path):
    store = SecretStore(tmp_path, use_keyring=False)
    store.set("a", "1")
    store.set("b", "2")
    store.delete("a")
    assert json.loads((tmp_path / "secrets.json").read_text()) == {"b": "2"}


def test_archivo_corrupto_no_rompe(tmp_path):
    (tmp_path / "secrets.json").write_text("{no es json")
    store = SecretStore(tmp_path, use_keyring=False)
    assert store.get("x") is None
    store.set("x", "y")
    assert store.get("x") == "y"
