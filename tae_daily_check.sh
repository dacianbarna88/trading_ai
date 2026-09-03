#!/bin/bash
# TAE daily check — single read-only command bundling the checks normally run by hand:
# health, today's decision trace, canonical vs PAPER accounting, V1 vs V2 verdict,
# and a sleep-gap check against the hourly-refresh heartbeat (catches missed cron runs
# caused by the Mac sleeping through the 10:00-22:00 schedule).
set -uo pipefail

SCRIPT_DIR="/Users/book/trading_ai_restored"
cd "$SCRIPT_DIR" || exit 1
PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

hr() { printf '%.0s=' {1..70}; echo; }

hr
echo "TAE DAILY CHECK — $(date '+%Y-%m-%d %H:%M:%S %Z')"
hr

echo
echo "--- Heartbeat / cron gap check ---"
HEARTBEAT_FILE="$SCRIPT_DIR/runtime_outputs/hourly_refresh/last_success.txt"
if [ -f "$HEARTBEAT_FILE" ]; then
    LAST=$(cat "$HEARTBEAT_FILE")
    echo "Last successful hourly-refresh (UTC): $LAST"
    LAST_EPOCH=$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$LAST" "+%s" 2>/dev/null)
    NOW_EPOCH=$(date -u "+%s")
    if [ -n "$LAST_EPOCH" ]; then
        GAP_MIN=$(( (NOW_EPOCH - LAST_EPOCH) / 60 ))
        echo "Gap since last successful run: ${GAP_MIN} min"
        [ "$GAP_MIN" -gt 90 ] && echo "WARNING: gap > 90 min — check if the Mac was asleep (pmset -g log | grep -i wake) or launchd job failed."
    fi
else
    echo "WARNING: heartbeat file not found — hourly refresh may never have run successfully."
fi

echo
echo "--- Health ---"
"$PYTHON_BIN" tae.py health 2>&1 | grep -E "CHECK MATRIX|\[OK\]|\[WARN\]|\[HEALTHY\]|Final quick verdict"

echo
echo "--- Today's decision trace (summary) ---"
"$PYTHON_BIN" tae.py today 2>&1 | sed -n '1,30p'
echo "..."
"$PYTHON_BIN" tae.py today 2>&1 | grep -E "FINAL VERDICT"

echo
echo "--- Canonical vs PAPER accounting ---"
"$PYTHON_BIN" tae.py canonical-vs-paper 2>&1 | sed -n '/| metric/,/## PAPER reconciliation/p'

echo
echo "--- V1 vs V2 verdict ---"
"$PYTHON_BIN" tae.py parallel-paper-report 2>&1 | tail -5

echo
echo "--- V1 vs V2 vs V3 verdict (Phase 5 soak) ---"
PP_HEARTBEAT="$SCRIPT_DIR/runtime_outputs/parallel_paper/hourly_trigger_last_success.txt"
if [ -f "$PP_HEARTBEAT" ]; then
    echo "Last parallel-paper (V1/V2/V3) run (UTC): $(cat "$PP_HEARTBEAT")"
else
    echo "WARNING: parallel-paper hourly-trigger heartbeat not found."
fi
"$PYTHON_BIN" tae.py parallel-paper-report-3way 2>&1 | tail -5
V3_RECON=$("$PYTHON_BIN" -c "
import json
try:
    d = json.load(open('$SCRIPT_DIR/runtime_outputs/parallel_paper/v3/accounting_snapshot.json'))
    print('reconciliation_pass=' + str(d.get('reconciliation_pass')) + ' ts=' + str(d.get('ts')))
except Exception as e:
    print('V3 accounting unreadable: ' + str(e))
")
echo "V3 accounting: $V3_RECON"
V3_ERRORS="$SCRIPT_DIR/runtime_outputs/parallel_paper/v3/errors.jsonl"
if [ -f "$V3_ERRORS" ]; then
    echo "WARNING: V3 errors.jsonl exists — tail:"
    tail -5 "$V3_ERRORS"
else
    echo "V3 errors: none"
fi

echo
echo "--- Activity watchdog (no-trade staleness + V3 feature coverage) ---"
# Added after a real incident: V3 sat at zero trades for 2 days with clean
# reconciliation/no errors the whole time — looked exactly like healthy,
# quiet inactivity from every other check in this script. This section
# exists so that specific failure mode can't hide again, for any arm.
# 72h threshold (not 24h) to tolerate a normal weekend without false alarms.
"$PYTHON_BIN" -c "
import json
from datetime import datetime, timezone

STALE_HOURS = 72
now = datetime.now(timezone.utc)

def last_trade_ts(path):
    try:
        with open(path) as fh:
            lines = fh.readlines()
        if not lines:
            return None
        last = json.loads(lines[-1])
        return last.get('ts') or last.get('timestamp')
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def parse(ts):
    try:
        return datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None

for arm, path in [
    ('V1', 'runtime_outputs/parallel_paper/v1/journals/trades.jsonl'),
    ('V2', 'runtime_outputs/parallel_paper/v2/journals/trades.jsonl'),
    ('V3', 'runtime_outputs/parallel_paper/v3/journals/trades.jsonl'),
    ('SHORT_MARGIN', 'runtime_outputs/parallel_paper/exp_short_margin/journals/trades.jsonl'),
]:
    ts = last_trade_ts(path)
    if ts is None:
        print(f'{arm}: NO TRADES EVER RECORDED — WARNING if arm has been enabled more than a day')
        continue
    dt = parse(ts)
    if dt is None:
        print(f'{arm}: last trade ts unparseable ({ts!r})')
        continue
    age_h = (now - dt).total_seconds() / 3600.0
    flag = 'WARNING: STALE' if age_h > STALE_HOURS else 'ok'
    print(f'{arm}: last trade {ts} ({age_h:.1f}h ago) — {flag}')

# V3 feature-coverage: fraction of today's V3 decisions that used real
# same-day PDE signal vs the neutral fallback. A sustained drop toward 0%
# is exactly the shape of the original silent bug — surfaced here instead
# of only being visible by reading raw decision JSON by hand.
today = now.date().isoformat()
total = enriched = 0
try:
    with open('runtime_outputs/parallel_paper/v3/journals/decisions.jsonl') as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(d.get('ts', '')).startswith(today) and d.get('p_profit') is not None:
                total += 1
                if d.get('pde_enriched'):
                    enriched += 1
except FileNotFoundError:
    pass
if total:
    pct = 100.0 * enriched / total
    flag = 'WARNING: LOW COVERAGE' if pct < 50.0 else 'ok'
    print(f'V3 feature coverage today: {enriched}/{total} scored decisions used real PDE signal ({pct:.0f}%) — {flag}')
else:
    print('V3 feature coverage today: no scored decisions yet')
"

hr
echo "Done. Read-only — no execution, no broker, no live changes."
hr
