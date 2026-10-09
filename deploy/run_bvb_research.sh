#!/bin/bash
# Weekly BVB signal snapshot (read-only -- never places an order; Alpaca
# doesn't support BVB anyway). Refreshes data/report so Dacian has an
# up-to-date trend+momentum signal to execute by hand at bt-trade.ro.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p state
PYTHON="venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') bvb research ====="
  caffeinate -i "$PYTHON" -c "
from bvb import data as bvb_data
from bvb import research
prices = bvb_data.load(refresh=True)
trend = research.trend_backtest(prices)
mom = research.momentum_backtest(prices)
sig = research.signal_today(prices)
text = research.to_markdown(trend, mom, sig)
path = research.write_report(text)
print(text)
print(f'Report written to {path}')
"
  echo "exit $?"
} >> state/bvb_launchd.log 2>&1
