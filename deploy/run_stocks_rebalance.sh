#!/bin/bash
# Daily engine pass for the stocks lab (MoVo10 paper account). Trades at most
# once per month-end decision; on every other day it logs "already_done" and
# exits. Paper only -- stocks/broker.py refuses any non-paper Alpaca URL.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p state
# launchd starts with a bare PATH: use the project venv, then python.org's Python.
PYTHON="venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') stocks rebalance ====="
  # caffeinate -i: the sequential 505-ticker fetch takes a few minutes --
  # don't let the Mac idle-sleep mid-run (the one-time wake from
  # deploy/arm_evening_wake.sh gets it running, not a guarantee it stays up).
  caffeinate -i "$PYTHON" -m stocks rebalance --submit  # strategy: momentum_vt10 (engine.DEFAULT_STRATEGY)
  echo "exit $?"
} >> state/stocks_launchd.log 2>&1
