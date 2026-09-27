#!/usr/bin/env bash
# Lanceur unique : délègue aux entry points du venv (installés par install.sh).
set -euo pipefail
ROMGET_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$ROMGET_ROOT/.venv/bin/romget" ]]; then
    echo 'Environnement absent : exécuter ./install.sh d'"'"'abord.' >&2
    exit 1
fi
if [[ "${1:-}" == '--cli' ]]; then shift; exec "$ROMGET_ROOT/.venv/bin/romget" "$@"; fi
exec "$ROMGET_ROOT/.venv/bin/romget-gui" "$@"
