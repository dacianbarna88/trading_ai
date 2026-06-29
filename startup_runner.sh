#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
LOG_FILE="$PROJECT_DIR/startup_runner.log"

cd "$PROJECT_DIR" || exit 1

# Default: live runtime. Opt-in dry-run only via --dry-run or STARTUP_DRY_RUN=1.
GUARD_ARGS=()
if [[ "${STARTUP_DRY_RUN:-0}" == "1" ]]; then
  GUARD_ARGS+=(--dry-run)
fi
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    GUARD_ARGS+=(--dry-run)
  fi
done

# Prevent inherited shell/cron dry-run from blocking real startup.
unset DRY_RUN TAE_DRY_RUN MARKET_GUARD_DRY_RUN

{
  echo ""
  echo "===== TRADING AI STARTUP RUNNER ====="
  echo "Timestamp: $(date)"
  echo "Reason: mac_login_or_reboot"
  echo "PROJECT_DIR: $PROJECT_DIR"
  echo "DRY_RUN: disabled (live startup default)"
  echo "GUARD_ARGS: ${GUARD_ARGS[*]:-none}"
  echo ""

  echo "[1/3] Starting Awake Guard..."
  /bin/bash "$PROJECT_DIR/awake_guard.sh"
  echo "OK"

  echo ""
  echo "[2/3] Running Market Session Guard (bot + dashboard if session open)..."
  if [ -x "$PYTHON_BIN" ]; then
    if ((${#GUARD_ARGS[@]})); then
      "$PYTHON_BIN" "$PROJECT_DIR/market_session_guard.py" "${GUARD_ARGS[@]}"
    else
      "$PYTHON_BIN" "$PROJECT_DIR/market_session_guard.py"
    fi
  else
    if ((${#GUARD_ARGS[@]})); then
      python3 "$PROJECT_DIR/market_session_guard.py" "${GUARD_ARGS[@]}"
    else
      python3 "$PROJECT_DIR/market_session_guard.py"
    fi
  fi

  echo ""
  echo "[3/3] Startup status..."
  if [ -f bot_pid.txt ]; then
    echo "Bot PID: $(cat bot_pid.txt)"
  else
    echo "Bot PID: MISSING"
  fi
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
