#!/bin/bash
# Install TAE periodic market-session-guard LaunchAgent (wake-safe, every 5 min).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
PLIST_TEMPLATE="$PROJECT_DIR/launchd/com.tradingai.market-session-guard.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.tradingai.market-session-guard.plist"
LABEL="com.tradingai.market-session-guard"
DOMAIN="gui/$(id -u)"

if [ ! -f "$PLIST_TEMPLATE" ]; then
  echo "ERROR: missing template $PLIST_TEMPLATE"
  exit 1
fi

chmod +x "$PROJECT_DIR/market_session_guard.sh"

PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

sed -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" -e "s|__PYTHON_BIN__|$PYTHON_BIN|g" \
  "$PLIST_TEMPLATE" > "$PLIST_DST"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST_DST"
launchctl enable "$DOMAIN/$LABEL"
launchctl kickstart -k "$DOMAIN/$LABEL" || true

echo "===== TAE MARKET SESSION GUARD LAUNCHAGENT INSTALLED ====="
echo "Plist: $PLIST_DST"
echo "Interval: 300s (5 min) | RunAtLoad: true"
echo "Scheduler source env: TAE_SCHEDULER_SOURCE=launchd"
echo ""
echo "Verify:"
echo "  launchctl list | grep tradingai"
echo "  tail -f $PROJECT_DIR/market_session_guard.log"
echo "  tail -f $PROJECT_DIR/market_session_guard_launchd.log"
