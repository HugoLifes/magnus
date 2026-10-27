#!/usr/bin/env bash
# Instala el daemon de Magnus en Linux para el usuario actual (sin root).
#
# Sirve para PCs con RTX, DGX Spark y Jetson sin Docker. En Jetson se recomienda
# Docker (deploy/docker-compose.jetson.yml): ver docs/INSTALL.md.
#
#   - copia Magnus a ~/.local/share/magnus/app
#   - crea un entorno de Python propio
#   - deja `magnus serve` como servicio systemd del usuario
#
# Uso, desde la raíz del repo:
#   bash deploy/linux/install.sh            # con servicio
#   bash deploy/linux/install.sh --sin-servicio

set -euo pipefail

SOURCE="$(cd "$(dirname "$0")/../.." && pwd)"
MAGNUS_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/magnus"
APP_DIR="$MAGNUS_HOME/app"
VENV_DIR="$MAGNUS_HOME/venv"
SERVICE=1
[[ "${1:-}" == "--sin-servicio" ]] && SERVICE=0

step() { printf '\033[36m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33mAviso: %s\033[0m\n' "$1"; }

step "Buscando Python 3.10 o superior"
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    PYTHON="$candidate"
    break
  fi
done
[[ -n "$PYTHON" ]] || { echo "No se encontró Python 3.10+ (en Ubuntu: sudo apt install python3 python3-venv)"; exit 1; }
"$PYTHON" -c 'import venv' 2>/dev/null || { echo "Falta el módulo venv (sudo apt install python3-venv)"; exit 1; }

command -v nvidia-smi >/dev/null 2>&1 || [[ -e /etc/nv_tegra_release ]] ||
  warn "no se detecta GPU NVIDIA (ni nvidia-smi ni Jetson)."
command -v ollama >/dev/null 2>&1 ||
  warn "no se encontró Ollama. Instálalo desde https://ollama.com/download"

step "Copiando Magnus a $APP_DIR"
mkdir -p "$APP_DIR"
for item in core daemon cli cloud skills agents; do
  rm -rf "${APP_DIR:?}/$item"
  cp -r "$SOURCE/$item" "$APP_DIR/$item"
done
cp "$SOURCE/pyproject.toml" "$SOURCE/requirements.txt" "$SOURCE/README.md" "$APP_DIR/"

step "Creando el entorno de Python"
"$PYTHON" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
# Editable: las skills y agentes incluidos se leen desde $APP_DIR.
"$VENV_DIR/bin/python" -m pip install --quiet -e "$APP_DIR"

if [[ "$SERVICE" == 1 ]] && command -v systemctl >/dev/null 2>&1; then
  step "Instalando el servicio systemd del usuario"
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/magnus.service" <<EOF
[Unit]
Description=Magnus: API local en http://127.0.0.1:8420
After=network-online.target

[Service]
ExecStart=$VENV_DIR/bin/magnus serve
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now magnus.service
fi

step "Comprobando el hardware"
"$VENV_DIR/bin/magnus" platform

printf '\n\033[32mMagnus instalado.\033[0m\n'
echo "  Estado del servicio: systemctl --user status magnus"
echo "  Modelos que caben:   $VENV_DIR/bin/magnus catalog"
echo "  Chat en terminal:    $VENV_DIR/bin/magnus chat <modelo>"
