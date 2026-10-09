#!/bin/bash
# Daily system health check, before markets open. Runs tests, validates
# both universes' price data, checks both Alpaca accounts, and re-runs each
# engine's own idempotent submit pass as a safe catch-up for anything the
# previous evening's job missed. See system_health_check.py's own
# docstring for exactly what this can and cannot fix.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p state
PYTHON="venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') health check ====="
  caffeinate -i "$PYTHON" system_health_check.py
  echo "exit $?"
} >> state/health_check_launchd.log 2>&1
