#!/bin/bash
# Install weekday scanner refresh cron — every 30 minutes Mon-Fri.
# Does NOT auto-promote watchlist.txt.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
BACKUP_FILE="/tmp/trading_ai_scanner_refresh_cron_backup_$(date +%Y%m%d_%H%M%S).txt"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

chmod +x "$PROJECT_DIR/tae_scanner_refresh.sh" 2>/dev/null || true

crontab -l > "$BACKUP_FILE" 2>/dev/null || true

CRON_FILE="/tmp/trading_ai_scanner_refresh_cron"
SCANNER_LINE="*/30 * * * 1-5 cd \"$PROJECT_DIR\" && TAE_SCHEDULER_SOURCE=cron /bin/bash \"$PROJECT_DIR/tae_scanner_refresh.sh\" >> \"$PROJECT_DIR/tae_scanner_refresh.log\" 2>&1"

# Preserve unrelated cron lines; remove prior scanner refresh rows only.
PRESERVE=$(
  crontab -l 2>/dev/null \
    | grep -v "$PROJECT_DIR/tae_scanner_refresh.sh" \
    | grep -v "tae_scanner_refresh" \
    || true
)

{
  [ -n "$PRESERVE" ] && echo "$PRESERVE"
  echo "$SCANNER_LINE"
} | awk 'NF && !seen[$0]++' > "$CRON_FILE"

crontab "$CRON_FILE"
rm "$CRON_FILE"

echo "===== TAE SCANNER REFRESH SCHEDULE INSTALLED ====="
echo ""
echo "Crontab backup: $BACKUP_FILE"
echo ""
echo "Cron (weekdays Mon-Fri):"
echo "  */30  tae_scanner_refresh.sh  (TAE_SCHEDULER_SOURCE=cron)"
echo ""
echo "Logs:"
echo "  $PROJECT_DIR/tae_scanner_refresh.log"
echo ""
echo "Manual run:"
echo "  bash $PROJECT_DIR/tae_scanner_refresh.sh"
echo ""
echo "Verify:"
echo "  crontab -l | grep tae_scanner_refresh"
echo ""
echo "Governance:"
echo "  - Refreshes scanner CSVs + candidate queue + proposal + audit"
echo "  - Does NOT write watchlist.txt"
echo "  - Does NOT auto-promote watchlist"
