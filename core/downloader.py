"""Descarga de modelos desde Hugging Face usando su CLI.

Magnus no reimplementa la descarga: envuelve la CLI oficial de Hugging Face
(`hf download`, o el antiguo `huggingface-cli download`). Esto corre en el
servidor con GPU, donde se quieren los pesos. Los modelos van a `models/`
(ignorado por git).

Para repos privados/gated, el usuario debe haber hecho `hf auth login` antes
(o exportar `HF_TOKEN`). Magnus no gestiona credenciales.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Orden de preferencia: CLI nueva (`hf`) y luego la antigua (`huggingface-cli`).
_HF_CLIS = ("hf", "huggingface-cli")


@dataclass
class HFDownloadResult:
    repo_id: str
    dest: str
    revision: str | None
    cli: str | None
    ok: bool
    message: str


def hf_cli_available() -> str | None:
    """Nombre de la CLI de HF disponible en el PATH, o None si no hay ninguna."""
    for name in _HF_CLIS:
        if shutil.which(name):
            return name
    return None


def _build_command(
    cli: str, repo_id: str, dest: Path, revision: str | None, allow_patterns: list[str] | None
) -> list[str]:
    # `hf download` y `huggingface-cli download` comparten flags.
    cmd = [cli, "download", repo_id, "--local-dir", str(dest)]
    if revision:
        cmd += ["--revision", revision]
    for pat in allow_patterns or []:
        cmd += ["--include", pat]
    return cmd


def download_model(
    repo_id: str,
    models_dir: str | Path = "models",
    revision: str | None = None,
    allow_patterns: list[str] | None = None,
    dry_run: bool = False,
) -> HFDownloadResult:
    """Descarga `repo_id` (p. ej. 'meta-llama/Llama-3.1-8B') a `models_dir/<repo>`.

    `allow_patterns` permite traer solo ciertos archivos — clave para bajar una
    cuantización concreta (p. ej. ['*Q4_K_M*.gguf']) en vez del repo entero.
    `dry_run=True` devuelve el comando sin ejecutarlo.
    """
    cli = hf_cli_available()
    dest = Path(models_dir) / repo_id.replace("/", "__")

    # En dry-run mostramos el comando aunque no haya CLI (asumimos 'hf').
    if dry_run:
        cmd = _build_command(cli or "hf", repo_id, dest, revision, allow_patterns)
        return HFDownloadResult(repo_id, str(dest), revision, cli, True, " ".join(cmd))

    if cli is None:
        return HFDownloadResult(
            repo_id, str(dest), revision, None, False,
            "No se encontró la CLI de Hugging Face. Instala con: pip install -U huggingface_hub[cli]",
        )

    cmd = _build_command(cli, repo_id, dest, revision, allow_patterns)

    dest.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(cmd, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        return HFDownloadResult(repo_id, str(dest), revision, cli, False, f"Falló la descarga: {exc}")
    return HFDownloadResult(repo_id, str(dest), revision, cli, True, f"Descargado en {dest}")
