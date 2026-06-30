#!/bin/bash
# Install weekday cron + wake-safe LaunchAgent for market session guard.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
BACKUP_FILE="/tmp/trading_ai_cron_backup_$(date +%Y%m%d_%H%M%S).txt"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

chmod +x "$PROJECT_DIR/startup_runner.sh" \
  "$PROJECT_DIR/market_session_guard.sh" \
  "$PROJECT_DIR/awake_guard.sh" \
  "$PROJECT_DIR/install_market_session_guard_agent.sh" 2>/dev/null || true

crontab -l > "$BACKUP_FILE" 2>/dev/null || true

CRON_FILE="/tmp/trading_ai_market_day_cron"
GUARD_LINE="*/5 * * * 1-5 cd \"$PROJECT_DIR\" && TAE_SCHEDULER_SOURCE=cron \"$PYTHON_BIN\" \"$PROJECT_DIR/market_session_guard.py\""
REBOOT_LINE="@reboot /bin/bash \"$PROJECT_DIR/startup_runner.sh\" >> \"$PROJECT_DIR/startup_runner.log\" 2>&1"

# Preserve unrelated user cron lines; drop all prior trading_ai schedule rows.
PRESERVE=$(crontab -l 2>/dev/null | grep -v "$PROJECT_DIR" | grep -v "trading_ai" | grep -v "daily_intelligence_runner" | grep -v "market_open_runner" | grep -v "market_close_runner" | grep -v "market_session_guard" | grep -v "startup_runner" || true)

{
  [ -n "$PRESERVE" ] && echo "$PRESERVE"
  echo "$GUARD_LINE"
  echo "*/30 * * * * cd \"$PROJECT_DIR\" && \"$PYTHON_BIN\" daily_intelligence_runner.py >> \"$PROJECT_DIR/scheduler_run.log\" 2>&1"
  echo "50 9 * * 1-5 cd \"$PROJECT_DIR\" && /bin/bash \"$PROJECT_DIR/market_open_runner.sh\" >> \"$PROJECT_DIR/market_open_runner.log\" 2>&1"
  echo "15 23 * * 1-5 cd \"$PROJECT_DIR\" && /bin/bash \"$PROJECT_DIR/market_close_runner.sh\" >> \"$PROJECT_DIR/market_close_runner.log\" 2>&1"
  echo "$REBOOT_LINE"
} | awk 'NF && !seen[$0]++' > "$CRON_FILE"

crontab "$CRON_FILE"
rm "$CRON_FILE"

echo "===== TAE MARKET DAY SCHEDULE INSTALLED ====="
echo ""
echo "Crontab backup: $BACKUP_FILE"
echo ""
echo "Cron (weekdays Mon-Fri):"
echo "  */5   market_session_guard.sh  (TAE_SCHEDULER_SOURCE=cron)"
echo "  */30  daily_intelligence_runner.py"
echo "  09:50 market_open_runner.sh"
echo "  23:15 market_close_runner.sh"
echo "  @reboot startup_runner.sh"
echo ""
echo "Installing LaunchAgent periodic guard (wake-safe primary)..."
/bin/bash "$PROJECT_DIR/install_market_session_guard_agent.sh"
echo ""
echo "Login autostart (optional, one-shot at login):"
echo "  ./install_autostart.sh"
echo ""
echo "Markets: EU / UK / US"
echo ""
echo "Verify installation:"
echo "  crontab -l | grep market_session_guard"
echo "  launchctl list | grep tradingai"
echo "  bash tae_market_open_monitor.sh"
