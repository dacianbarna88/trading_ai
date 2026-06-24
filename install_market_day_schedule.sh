#!/bin/bash

PROJECT_DIR="/Users/book/Desktop/trading_ai"
PYTHON_BIN="/Users/book/Desktop/trading_ai/venv/bin/python3"

CRON_FILE="/tmp/trading_ai_market_day_cron"

cat > "$CRON_FILE" <<EOF
*/30 * * * * cd "$PROJECT_DIR" && "$PYTHON_BIN" daily_intelligence_runner.py >> scheduler_run.log 2>&1
50 9 * * 1-5 cd "$PROJECT_DIR" && ./market_open_runner.sh >> market_open_runner.log 2>&1
15 23 * * 1-5 cd "$PROJECT_DIR" && ./market_close_runner.sh >> market_close_runner.log 2>&1
EOF

crontab "$CRON_FILE"
rm "$CRON_FILE"

echo "===== V34.5 MARKET DAY SCHEDULE INSTALLED ====="
echo ""
echo "09:45  macOS wake configured separately"
echo "09:50  Market Open Runner"
echo "Every 30 min Daily Intelligence Runner"
echo "23:15  Market Close Runner + Backup + Sleep"
echo ""
echo "Markets covered:"
echo "EU / UK / US"
