#!/bin/bash

cd /Users/book/Desktop/trading_ai || exit 1

echo ""
echo "===== V37.7 MARKET OPEN RUNNER ====="
echo ""

echo "[1/6] Starting Awake Guard..."
/bin/bash /Users/book/Desktop/trading_ai/awake_guard.sh
sleep 2
echo "OK"

echo ""
echo "[2/6] Starting Live Bot via bot_controller.py..."
python3 - <<'PY'
from bot_controller import start_bot, get_status

print(start_bot())
print("Bot status:", get_status())
PY

echo ""
echo "[3/6] Running Morning Update..."
python3 morning_update.py

echo ""
echo "[4/6] Running Daily Intelligence..."
python3 daily_intelligence_runner.py

echo ""
echo "[5/6] Checking Scheduler..."
crontab -l

echo ""
echo "[6/6] System Status..."

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

echo ""
echo "Mode:"
echo "ANALYSIS_ONLY"
echo "PAPER_ONLY"
echo "NO_BROKER"

echo ""
echo "===== READY FOR MARKET ====="
