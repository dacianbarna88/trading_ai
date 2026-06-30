#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

echo "===== TAE STARTUP VERIFY ====="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "[1/4] Running startup_runner.sh ..."
set +e
/bin/bash "$SCRIPT_DIR/startup_runner.sh"
STARTUP_RC=$?
set -e
echo "startup_runner exit: $STARTUP_RC"

echo ""
echo "[2/4] Waiting 3s for processes to settle ..."
sleep 3

echo ""
echo "[3/4] Running market open monitor ..."
set +e
"$PYTHON_BIN" "$SCRIPT_DIR/tae_market_open_monitor.py"
MONITOR_RC=$?
set -e
echo "monitor exit: $MONITOR_RC"

echo ""
echo "[4/4] Running ecosystem review ..."
set +e
/bin/bash "$SCRIPT_DIR/tae_full_ecosystem_review.sh"
REVIEW_RC=$?
set -e
echo "ecosystem review exit: $REVIEW_RC"

echo ""
"$PYTHON_BIN" "$SCRIPT_DIR/tae_startup_verify.py" "$STARTUP_RC" "$MONITOR_RC" "$REVIEW_RC"
VERIFY_RC=$?

echo ""
echo "Outputs:"
echo "  tae_market_open_monitor.json"
echo "  tae_market_open_monitor.md"
echo "  tae_startup_verify.json"
echo "  tae_startup_verify.md"

exit "$VERIFY_RC"
