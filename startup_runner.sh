#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/book/Desktop/trading_ai"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
LOG_FILE="$PROJECT_DIR/startup_runner.log"

cd "$PROJECT_DIR" || exit 1

{
  echo ""
  echo "===== TRADING AI STARTUP RUNNER ====="
  echo "Timestamp: $(date)"
  echo "Reason: mac_login_or_reboot"
  echo ""

  echo "[1/3] Starting Awake Guard..."
  /bin/bash "$PROJECT_DIR/awake_guard.sh"
  echo "OK"

  echo ""
  echo "[2/3] Running Market Session Guard (bot + dashboard if session open)..."
  if [ -x "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" "$PROJECT_DIR/market_session_guard.py"
  else
    python3 "$PROJECT_DIR/market_session_guard.py"
  fi

  echo ""
  echo "[3/3] Startup status..."
  if [ -f bot_status.txt ]; then
    echo "Bot Status: $(cat bot_status.txt)"
  fi
  if [ -f dashboard_status.txt ]; then
    echo "Dashboard Status: $(cat dashboard_status.txt)"
  fi

  echo ""
  echo "Mode: ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"
  echo "===== STARTUP COMPLETE ====="
} >> "$LOG_FILE" 2>&1
