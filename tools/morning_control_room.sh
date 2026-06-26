#!/bin/bash
# TAE Morning Control Room — read-only daily health dashboard.
# No broker. No execution. No data edits. No kill/git commit.

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

TODAY="$(date +%Y-%m-%d)"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S %Z')"

section() {
    echo ""
    echo "===== $1 ====="
}

print_file_tail() {
    local file="$1"
    local lines="$2"
    if [[ -f "$file" ]]; then
        tail -n "$lines" "$file"
    else
        echo "[MISSING] $file"
    fi
}

# --- 1. Header ---
echo "TAE MORNING CONTROL ROOM"
echo "$TIMESTAMP"
echo "Project: $PROJECT_DIR"
echo "Read-only | No broker | No execution"

# --- 2. Bot / process health ---
section "BOT / PROCESS HEALTH"

STREAMLIT_PROCS="$(pgrep -fl streamlit 2>/dev/null || true)"
DASHBOARD_PROCS="$(pgrep -fl "dashboard_v2" 2>/dev/null || true)"
DASHBOARD_PORT=""
for port in 8501 8502 8503; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        DASHBOARD_PORT="$port"
        break
    fi
done

if [[ -n "$STREAMLIT_PROCS" ]]; then
    echo "Streamlit dashboard: RUNNING"
    echo "$STREAMLIT_PROCS" | while IFS= read -r line; do
        echo "  $line"
    done
elif [[ -n "$DASHBOARD_PROCS" ]]; then
    echo "Streamlit dashboard: RUNNING (dashboard_v2 process)"
    echo "$DASHBOARD_PROCS" | while IFS= read -r line; do
        echo "  $line"
    done
elif [[ -n "$DASHBOARD_PORT" ]]; then
    echo "Streamlit dashboard: RUNNING (listener on port $DASHBOARD_PORT)"
else
    echo "Streamlit dashboard: NOT DETECTED"
fi

if [[ -n "$DASHBOARD_PORT" ]]; then
    echo "Dashboard port: $DASHBOARD_PORT (LISTEN)"
    lsof -nP -iTCP:"$DASHBOARD_PORT" -sTCP:LISTEN 2>/dev/null | while IFS= read -r line; do
        echo "  $line"
    done
else
    echo "Dashboard port: not listening on 8501-8503"
fi

CAFFEINATE_PROCS="$(pgrep -fl caffeinate 2>/dev/null || true)"
if [[ -n "$CAFFEINATE_PROCS" ]]; then
    echo "Caffeinate: ACTIVE"
    echo "$CAFFEINATE_PROCS" | while IFS= read -r line; do
        echo "  $line"
    done
else
    echo "Caffeinate: NOT ACTIVE"
fi

BOT_PROCS="$(pgrep -fl "python.*live_bot" 2>/dev/null || true)"
if [[ -n "$BOT_PROCS" ]]; then
    echo "Python bot (live_bot): DETECTED"
    echo "$BOT_PROCS" | while IFS= read -r line; do
        echo "  $line"
    done
else
    echo "Python bot (live_bot): NOT DETECTED"
fi

if [[ -f bot_pid.txt ]]; then
    echo "bot_pid.txt: $(tr -d '\n' < bot_pid.txt)"
fi
if [[ -f bot_status.txt ]]; then
    echo "bot_status.txt: $(tr -d '\n' < bot_status.txt)"
fi

# --- 3. Market regime ---
section "MARKET REGIME (last 5 from bot_output.log)"
if [[ -f bot_output.log ]]; then
    grep -F "Market Regime" bot_output.log 2>/dev/null | tail -n 5 || echo "(no Market Regime lines found)"
else
    echo "[MISSING] bot_output.log"
fi

# --- 4. Recent bot activity ---
section "RECENT BOT ACTIVITY (last 20 lines, bot_output.log)"
print_file_tail bot_output.log 20

# --- 5. Portfolio ---
section "PORTFOLIO (last 20 lines, portfolio.csv)"
print_file_tail portfolio.csv 20

section "PORTFOLIO TODAY BUY ($TODAY)"
if [[ -f portfolio.csv ]]; then
    awk -F',' -v today="$TODAY" '
        NR == 1 { next }
        index($1, today) == 1 && $3 == "BUY" { print }
    ' portfolio.csv
    buy_count=$(awk -F',' -v today="$TODAY" 'NR>1 && index($1,today)==1 && $3=="BUY" {c++} END {print c+0}' portfolio.csv)
    if [[ "$buy_count" -eq 0 ]]; then
        echo "(no BUY rows for $TODAY)"
    fi
else
    echo "[MISSING] portfolio.csv"
fi

section "PORTFOLIO TODAY SELL ($TODAY)"
if [[ -f portfolio.csv ]]; then
    awk -F',' -v today="$TODAY" '
        NR == 1 { next }
        index($1, today) == 1 && $3 == "SELL" { print }
    ' portfolio.csv
    sell_count=$(awk -F',' -v today="$TODAY" 'NR>1 && index($1,today)==1 && $3=="SELL" {c++} END {print c+0}' portfolio.csv)
    if [[ "$sell_count" -eq 0 ]]; then
        echo "(no SELL rows for $TODAY)"
    fi
else
    echo "[MISSING] portfolio.csv"
fi

# --- 6. Live signals ---
section "LIVE SIGNALS (top 20, live_signals.csv)"
if [[ -f live_signals.csv ]]; then
    head -n 21 live_signals.csv
else
    echo "[MISSING] live_signals.csv"
fi

section "STRONG BUY LIST"
if [[ -f live_signals.csv ]]; then
    awk -F',' 'NR == 1 { next } $7 == "STRONG BUY" { printf "%-20s score=%s price=%s\n", $2, $6, $3 }' live_signals.csv
    count="$(awk -F',' 'NR>1 && $7=="STRONG BUY" {c++} END {print c+0}' live_signals.csv)"
    if [[ "$count" -eq 0 ]]; then
        echo "(none)"
    fi
else
    echo "[MISSING] live_signals.csv"
fi

section "TAKE PROFIT LIST"
if [[ -f live_signals.csv ]]; then
    awk -F',' 'NR == 1 { next } $7 == "TAKE PROFIT" { printf "%-20s score=%s price=%s\n", $2, $6, $3 }' live_signals.csv
    count="$(awk -F',' 'NR>1 && $7=="TAKE PROFIT" {c++} END {print c+0}' live_signals.csv)"
    if [[ "$count" -eq 0 ]]; then
        echo "(none)"
    fi
else
    echo "[MISSING] live_signals.csv"
fi

# --- 7. Research artifacts ---
section "RESEARCH ARTIFACTS"
check_artifact() {
    local file="$1"
    if [[ -f "$file" ]]; then
        echo "[OK]      $file"
    else
        echo "[MISSING] $file"
    fi
}
check_artifact tae_learning_report.json
check_artifact tae_research_priorities.json
check_artifact tae_cross_validation_report.json
check_artifact tae_knowledge_candidates.json
check_artifact tae_discoveries.json

# --- 8. Git ---
section "GIT"
if git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    GIT_SHORT="$(git -C "$PROJECT_DIR" status --short 2>/dev/null || true)"
    if [[ -z "$GIT_SHORT" ]]; then
        echo "GIT CLEAN"
    else
        echo "GIT DIRTY"
        git -C "$PROJECT_DIR" status --short
    fi
else
    echo "GIT: not a repository"
    GIT_SHORT="dirty"
fi

# --- 9. Overall status ---
section "OVERALL STATUS"

HEALTHY=true
DASHBOARD_RUNNING=false
if [[ -n "$(pgrep -f streamlit 2>/dev/null || true)" ]] \
    || [[ -n "$(pgrep -f dashboard_v2 2>/dev/null || true)" ]] \
    || [[ -n "$DASHBOARD_PORT" ]]; then
    DASHBOARD_RUNNING=true
fi

if [[ "$DASHBOARD_RUNNING" != true ]]; then
    HEALTHY=false
    echo "  [check] streamlit dashboard not detected"
fi
if [[ ! -f bot_output.log ]]; then
    HEALTHY=false
    echo "  [check] bot_output.log missing"
fi
if [[ ! -f live_signals.csv ]]; then
    HEALTHY=false
    echo "  [check] live_signals.csv missing"
fi
if [[ ! -f portfolio.csv ]]; then
    HEALTHY=false
    echo "  [check] portfolio.csv missing"
fi
if [[ -n "$GIT_SHORT" ]]; then
    HEALTHY=false
    echo "  [check] git not clean"
fi

if [[ "$HEALTHY" == true ]]; then
    echo "SYSTEM HEALTHY"
else
    echo "CHECK REQUIRED"
fi

echo ""
echo "End of morning control room. Read-only — no actions taken."
