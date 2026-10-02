#!/bin/bash
# Daily engine pass (paper only). Trades at most once per month-end decision;
# on every other day it logs "already_done" and exits.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p state
# launchd starts with a bare PATH: use the project venv, then python.org's Python.
PYTHON="venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') rebalance ====="
  # caffeinate -i: don't let the Mac idle-sleep mid-run (it was just woken
  # by deploy/arm_evening_wake.sh for exactly this window, but that's a
  # one-time wake, not a guarantee it stays up for the run's duration).
  caffeinate -i "$PYTHON" -m tae2 rebalance --submit  # strategy from TAE2_STRATEGY in .env
  echo "exit $?"
} >> state/launchd.log 2>&1
