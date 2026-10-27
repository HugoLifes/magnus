"""Punto de entrada de `magnus.exe` cuando se congela con PyInstaller (ver build-installer.ps1)."""

from cli.main import app

if __name__ == "__main__":
    app()
