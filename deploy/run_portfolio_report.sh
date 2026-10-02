#!/bin/bash
# Nightly portfolio report, both paper accounts (tae2 + stocks/MoVo10).
# Read-only -- never places an order. Runs after the US market closes.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p state
PYTHON="venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') portfolio report ====="
  # caffeinate -i: don't let the Mac idle-sleep mid-run (woken by
  # deploy/arm_evening_wake.sh for this window, which is a one-time wake,
  # not a guarantee it stays up for the run's duration).
  caffeinate -i "$PYTHON" portfolio_report.py
  echo "exit $?"
} >> state/portfolio_report_launchd.log 2>&1
