#!/bin/bash

PROJECT_DIR="/Users/book/Desktop/trading_ai"
PYTHON_BIN="/Users/book/Desktop/trading_ai/venv/bin/python3"
BACKUP_FILE="/tmp/trading_ai_cron_backup_$(date +%Y%m%d_%H%M%S).txt"

if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

crontab -l > "$BACKUP_FILE" 2>/dev/null || true

CRON_FILE="/tmp/trading_ai_market_day_cron"
GUARD_LINE='*/10 * * * 1-5 cd "/Users/book/Desktop/trading_ai" && /bin/bash /Users/book/Desktop/trading_ai/market_session_guard.sh >> /Users/book/Desktop/trading_ai/market_session_guard.log 2>&1'
REBOOT_LINE='@reboot /bin/bash /Users/book/Desktop/trading_ai/startup_runner.sh >> /Users/book/Desktop/trading_ai/startup_runner.log 2>&1'

{
    crontab -l 2>/dev/null || true
    echo "$GUARD_LINE"
    echo '*/30 * * * * cd "/Users/book/Desktop/trading_ai" && "/Users/book/Desktop/trading_ai/venv/bin/python3" daily_intelligence_runner.py >> scheduler_run.log 2>&1'
    echo '50 9 * * 1-5 cd "/Users/book/Desktop/trading_ai" && /bin/bash /Users/book/Desktop/trading_ai/market_open_runner.sh >> market_open_runner.log 2>&1'
    echo '15 23 * * 1-5 cd "/Users/book/Desktop/trading_ai" && /bin/bash /Users/book/Desktop/trading_ai/market_close_runner.sh >> market_close_runner.log 2>&1'
    echo "$REBOOT_LINE"
} | awk '!seen[$0]++' > "$CRON_FILE"

crontab "$CRON_FILE"
rm "$CRON_FILE"

echo "===== V37.8 MARKET DAY SCHEDULE INSTALLED ====="
echo ""
echo "Crontab backup: $BACKUP_FILE"
echo "@reboot  Startup Runner (bot/dashboard/awake if session open)"
echo "*/10     Market Session Guard (EU/UK/US aware)"
echo "09:50    Market Open Runner"
echo "Every 30 min Daily Intelligence Runner"
echo "23:15    Market Close Runner + Backup + Sleep"
echo ""
echo "LaunchAgent install (login autostart):"
echo "  ./install_autostart.sh"
echo ""
echo "Markets covered:"
echo "EU / UK / US (ASIA configured disabled)"
