#!/bin/bash

cd /Users/book/Desktop/trading_ai

echo ""
echo "===== V34.5 MARKET CLOSE RUNNER ====="
echo ""

echo "[1/4] Running Daily Intelligence..."
python3 daily_intelligence_runner.py

echo ""
echo "[2/4] Running Full Backup..."
python3 full_backup_runner.py

echo ""
echo "[3/4] Stopping Awake Guard..."
pkill caffeinate 2>/dev/null
echo "Awake Guard stopped"

echo ""
echo "[4/4] Sleeping Mac..."
echo "Market day complete. Going to sleep."

pmset sleepnow
