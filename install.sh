#!/usr/bin/env bash
# Installation isolée dans le projet ; aucune modification du Python système.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || {
    echo 'Python 3.11+ requis.' >&2; exit 1;
}
python3 -m venv .venv || {
    echo 'venv/pip indisponible. Installer leur paquet système.' >&2; exit 1;
}
.venv/bin/python -m pip install --editable .
.venv/bin/python -c 'from PySide6 import QtWidgets' || {
    echo 'PySide6 incomplet : réinstaller le paquet dans le venv.' >&2; exit 1;
}
echo 'Installation terminée : .venv/bin/cochwa ou .venv/bin/cochwa-gui (alias romget* conservés)'
