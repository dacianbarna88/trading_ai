#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"

cd "$PROJECT_DIR" || exit 1

GUARD_ARGS=()
for arg in "$@"; do
  GUARD_ARGS+=("$arg")
done

# Live runtime default — ignore inherited DRY_RUN unless --dry-run passed to this script.
unset DRY_RUN TAE_DRY_RUN MARKET_GUARD_DRY_RUN

if [ -x "$PYTHON_BIN" ]; then
  exec "$PYTHON_BIN" "$PROJECT_DIR/market_session_guard.py" "${GUARD_ARGS[@]}"
else
  exec python3 "$PROJECT_DIR/market_session_guard.py" "${GUARD_ARGS[@]}"
fi
