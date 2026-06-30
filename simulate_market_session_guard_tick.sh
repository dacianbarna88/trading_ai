#!/bin/bash
# Simulate one scheduled guard tick (same as LaunchAgent/cron would invoke).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export TAE_SCHEDULER_SOURCE="${TAE_SCHEDULER_SOURCE:-simulate}"
PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"
echo "Simulating scheduled guard tick (scheduler=$TAE_SCHEDULER_SOURCE)"
exec "$PYTHON_BIN" "$SCRIPT_DIR/market_session_guard.py" "$@"
