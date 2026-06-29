#!/bin/bash

cd /Users/book/Desktop/trading_ai || exit 1

PYTHON_BIN="/Users/book/Desktop/trading_ai/venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

echo ""
echo "===== V37.8 MARKET OPEN RUNNER ====="
echo "Timestamp: $(date)"
echo "Reason: scheduled_market_open_runner"
echo ""

echo "[1/7] Starting Awake Guard..."
/bin/bash /Users/book/Desktop/trading_ai/awake_guard.sh
sleep 2
echo "OK"

echo ""
echo "[2/7] Starting Live Bot via bot_controller.py..."
"$PYTHON_BIN" - <<'PY'
from bot_controller import start_bot, get_status

print(start_bot())
print("Bot status:", get_status())
PY

echo ""
echo "[3/7] Starting Dashboard via bot_controller.py..."
"$PYTHON_BIN" - <<'PY'
from bot_controller import start_dashboard, get_dashboard_status

print(start_dashboard())
print("Dashboard status:", get_dashboard_status())
PY

echo ""
echo "[4/7] Running Morning Update..."
"$PYTHON_BIN" morning_update.py

echo ""
echo "[5/7] Running Daily Intelligence..."
"$PYTHON_BIN" daily_intelligence_runner.py

echo ""
echo "[6/7] Running Market Session Guard..."
"$PYTHON_BIN" market_session_guard.py

echo ""
echo "[7/7] System Status..."

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
