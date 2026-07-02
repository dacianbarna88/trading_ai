#!/bin/bash
set -eo pipefail

PROJECT_DIR="/Users/book/Desktop/trading_ai"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
LOG_FILE="$PROJECT_DIR/startup_runner.log"

cd "$PROJECT_DIR" || exit 1

GUARD_ARGS=()
if [[ "${STARTUP_DRY_RUN:-0}" == "1" ]]; then
  GUARD_ARGS+=(--dry-run)
fi
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    GUARD_ARGS+=(--dry-run)
  fi
done

unset DRY_RUN TAE_DRY_RUN MARKET_GUARD_DRY_RUN

log_section() {
  {
    echo ""
    echo "===== TRADING AI STARTUP RUNNER ====="
    echo "Timestamp: $(date)"
    echo "Reason: ${TAE_SCHEDULER_SOURCE:-manual}_startup"
    echo "PROJECT_DIR: $PROJECT_DIR"
    echo "DRY_RUN: disabled (live startup default)"
    if ((${#GUARD_ARGS[@]})); then
      echo "GUARD_ARGS: ${GUARD_ARGS[*]}"
    else
      echo "GUARD_ARGS: none"
    fi
    echo ""

    echo "[1/3] Starting Awake Guard..."
    /bin/bash "$PROJECT_DIR/awake_guard.sh"
    echo "OK"

    echo ""
    echo "[2/3] Market Session Guard pre-check..."
    BOT_RUNNING=false
    DASH_RUNNING=false
    if pgrep -f "live_bot.py" > /dev/null 2>&1; then
      BOT_RUNNING=true
      echo "STARTUP: live_bot already running"
    fi
    if pgrep -f "streamlit run dashboard_v2.py" > /dev/null 2>&1; then
      DASH_RUNNING=true
      echo "STARTUP: dashboard already running"
    fi

    if $BOT_RUNNING && $DASH_RUNNING; then
      echo "STARTUP: skipping market_session_guard (bot and dashboard already up)"
    else
      if ! $BOT_RUNNING; then
        echo "STARTUP: starting live_bot via market_session_guard"
      fi
      if ! $DASH_RUNNING; then
        echo "STARTUP: starting dashboard via market_session_guard"
      fi
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
    fi

    echo ""
    echo "[3/3] Startup status..."
    if [ -f "$PROJECT_DIR/bot_pid.txt" ]; then
      echo "Bot PID: $(cat "$PROJECT_DIR/bot_pid.txt")"
    else
      echo "Bot PID: MISSING"
    fi
    if [ -f "$PROJECT_DIR/bot_status.txt" ]; then
      echo "Bot Status: $(cat "$PROJECT_DIR/bot_status.txt")"
    fi
    if [ -f "$PROJECT_DIR/dashboard_status.txt" ]; then
      echo "Dashboard Status: $(cat "$PROJECT_DIR/dashboard_status.txt")"
    fi

    echo ""
    echo "Mode: ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"
    echo "===== STARTUP COMPLETE ====="
  } >> "$LOG_FILE" 2>&1
}

log_section
