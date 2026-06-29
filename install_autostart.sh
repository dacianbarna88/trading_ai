#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/book/Desktop/trading_ai"
PLIST_SRC="$PROJECT_DIR/launchd/com.tradingai.startup.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.tradingai.startup.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DST"
launchctl bootout "gui/$(id -u)/com.tradingai.startup" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl enable "gui/$(id -u)/com.tradingai.startup"
launchctl kickstart -k "gui/$(id -u)/com.tradingai.startup"

echo "===== TRADING AI AUTOSTART INSTALLED ====="
echo "LaunchAgent: $PLIST_DST"
echo "Runs on login: startup_runner.sh"
echo ""
echo "Manual test:"
echo "  /bin/bash $PROJECT_DIR/startup_runner.sh"
echo "  tail -f $PROJECT_DIR/startup_runner.log"
