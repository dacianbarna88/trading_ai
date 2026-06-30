#!/bin/bash
# TAE X.10C — Scanner refresh wrapper (runtime data refresh only; never writes watchlist.txt)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
  PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/tae_scanner_refresh.py" "$@"
