#!/bin/bash

LOG_FILE="/Users/book/Desktop/trading_ai/market_open_runner.log"
mkdir -p "$(dirname "$LOG_FILE")"

# Initialize log at the very top (append, never truncate) and mirror to terminal.
{
    echo ""
    echo "===== MARKET OPEN RUNNER LOG SESSION ====="
    echo "Log file: $LOG_FILE"
    echo "Started: $(date)"
    echo "Shell: $$ PPID: $PPID"
    echo ""
} | tee -a "$LOG_FILE"

_tae_market_open_runner_main() {
    cd /Users/book/Desktop/trading_ai || return 1

    PYTHON_BIN="/Users/book/Desktop/trading_ai/venv/bin/python3"
    if [ ! -x "$PYTHON_BIN" ]; then
        PYTHON_BIN="python3"
    fi

    echo ""
    echo "===== V37.8 MARKET OPEN RUNNER ====="
    echo "Timestamp: $(date)"
    echo "Reason: scheduled_market_open_runner"
    echo ""

    echo "[1/8] Starting Awake Guard..."
    /bin/bash /Users/book/Desktop/trading_ai/awake_guard.sh
    sleep 2
    echo "OK"

    echo ""
    echo "[2/8] Starting Live Bot via bot_controller.py..."
    if pgrep -f "live_bot.py" > /dev/null 2>&1; then
        echo "SKIP: live_bot.py already running (pgrep)"
    else
        "$PYTHON_BIN" - <<'PY'
from bot_controller import start_bot, get_status

print(start_bot())
print("Bot status:", get_status())
PY
    fi

    echo ""
    echo "[3/8] Starting Dashboard via bot_controller.py..."
    if pgrep -f "streamlit run dashboard_v2.py" > /dev/null 2>&1; then
        echo "SKIP: dashboard already running (pgrep)"
    else
        "$PYTHON_BIN" - <<'PY'
from bot_controller import start_dashboard, get_dashboard_status

print(start_dashboard())
print("Dashboard status:", get_dashboard_status())
PY
    fi

    echo ""
    echo "[4/8] Running Market Open Intelligence Stack (SHADOW_ONLY)..."
    if pgrep -f "tae_market_open_intelligence_runner.py" > /dev/null 2>&1; then
        echo "SKIP: tae_market_open_intelligence_runner.py already running (pgrep)"
    else
        if "$PYTHON_BIN" tae_market_open_intelligence_runner.py >> market_open_intelligence_runner.log 2>&1; then
            echo "OK"
        else
            echo "WARN: intelligence runner exited non-zero — live bot continues"
        fi
    fi

    echo ""
    echo "[5/8] Running Morning Update..."
    "$PYTHON_BIN" morning_update.py

    echo ""
    echo "[6/8] Running Daily Intelligence..."
    "$PYTHON_BIN" daily_intelligence_runner.py

    echo ""
    echo "[7/8] Running Market Session Guard..."
    "$PYTHON_BIN" market_session_guard.py

    echo ""
    echo "[8/8] System Status..."

    echo "Trading AI READY"
    echo "Scheduler ACTIVE"
    echo "Awake Guard ACTIVE"

    if [ -f bot_pid.txt ]; then
        echo "Bot PID: $(cat bot_pid.txt)"
    else
        echo "Bot PID: MISSING"
    fi

    if [ -f bot_status.txt ]; then
        echo "Bot Status: $(cat bot_status.txt)"
    else
        echo "Bot Status: MISSING"
    fi

    if [ -f dashboard_status.txt ]; then
        echo "Dashboard Status: $(cat dashboard_status.txt)"
    else
        echo "Dashboard Status: MISSING"
    fi

    echo ""
    echo "Mode:"
    echo "ANALYSIS_ONLY"
    echo "PAPER_ONLY"
    echo "NO_BROKER"
    echo "NO_EXECUTION"

    echo ""
    echo "===== READY FOR MARKET ====="
    echo "Finished: $(date)"
    echo "===== END MARKET OPEN RUNNER ====="
}

# Append runner output to log while preserving terminal visibility; keep real exit code.
_tae_market_open_runner_main 2>&1 | tee -a "$LOG_FILE"
exit "${PIPESTATUS[0]}"
