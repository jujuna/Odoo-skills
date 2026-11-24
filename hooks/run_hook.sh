#!/usr/bin/env sh
# Portable hook launcher: prefers workspace Odoo venv Python, falls back to python3.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT="${CLAUDE_PROJECT_DIR:-$(dirname -- "$(dirname -- "$SCRIPT_DIR")")}"
HOOK="$SCRIPT_DIR/$1"
shift
for PY in "$ROOT/data_venv/bin/python" "$ROOT/.venv/bin/python" "$ROOT/venv/bin/python" "$ROOT/env/bin/python"; do
    if [ -x "$PY" ]; then
        exec "$PY" "$HOOK" "$@"
    fi
done
exec python3 "$HOOK" "$@"
