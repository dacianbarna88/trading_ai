#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/book/Desktop/trading_ai"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
LOG_FILE="$PROJECT_DIR/market_session_guard.log"

cd "$PROJECT_DIR" || exit 1

"$PYTHON_BIN" "$PROJECT_DIR/market_session_guard.py"
