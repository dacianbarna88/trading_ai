#!/bin/bash

PROJECT_DIR="/Users/book/Desktop/trading_ai"
PYTHON_BIN="/Users/book/Desktop/trading_ai/venv/bin/python3"

CRON_FILE="/tmp/trading_ai_cron"

cat > "$CRON_FILE" <<EOF
*/30 * * * * cd "$PROJECT_DIR" && "$PYTHON_BIN" daily_intelligence_runner.py >> scheduler_run.log 2>&1
EOF

crontab "$CRON_FILE"

rm "$CRON_FILE"

echo "===== V34.2 MARKET SCHEDULER INSTALLED ====="
echo "Runs every 30 minutes:"
echo "python3 daily_intelligence_runner.py"
echo ""
echo "Project:"
echo "$PROJECT_DIR"
echo ""
echo "Log:"
echo "scheduler_run.log"
