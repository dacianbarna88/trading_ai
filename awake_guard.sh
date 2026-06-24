#!/bin/bash

cd /Users/book/Desktop/trading_ai

PID_FILE="awake_guard.pid"
LOG_FILE="awake_guard.log"

echo "===== AWAKE GUARD =====" >> "$LOG_FILE"
echo "Timestamp: $(date)" >> "$LOG_FILE"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Already running PID: $OLD_PID" >> "$LOG_FILE"
        exit 0
    else
        echo "Stale PID removed: $OLD_PID" >> "$LOG_FILE"
        rm -f "$PID_FILE"
    fi
fi

nohup caffeinate -d -i -m >> "$LOG_FILE" 2>&1 &
NEW_PID=$!

echo "$NEW_PID" > "$PID_FILE"
echo "Started caffeinate PID: $NEW_PID" >> "$LOG_FILE"
echo "Status: ACTIVE" >> "$LOG_FILE"
