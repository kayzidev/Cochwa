#!/usr/bin/env bash
# Lanceur unique : délègue aux entry points du venv (installés par install.sh).
set -euo pipefail
COCHWA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$COCHWA_ROOT/.venv/bin/cochwa" ]]; then
    echo 'Environnement absent : exécuter ./install.sh d'"'"'abord.' >&2
    exit 1
fi
if [[ "${1:-}" == '--cli' ]]; then shift; exec "$COCHWA_ROOT/.venv/bin/cochwa" "$@"; fi
exec "$COCHWA_ROOT/.venv/bin/cochwa-gui" "$@"
