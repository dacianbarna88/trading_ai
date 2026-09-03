#!/bin/bash
# TAE hourly refresh — live_bot.py single-shot (live_signals.csv refresh) + full-paper-cycle.
# live_bot.py has no --once flag (confirmed by investigation: running it directly enters
# an infinite while-loop) — the single-shot equivalent is calling generate_signals()
# directly, which runs exactly one cycle and returns.
set -uo pipefail

SCRIPT_DIR="/Users/book/trading_ai_restored"
cd "$SCRIPT_DIR" || exit 1

PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') hourly refresh start ====="

"$PYTHON_BIN" -c "
import live_bot
live_bot.set_status('RUNNING')
live_bot.log('Live bot pornit (single-shot, hourly launchd).')
live_bot.generate_signals()
live_bot.set_status('STOPPED')
live_bot.log('Live bot oprit (single-shot complet).')
"

echo "----- live_bot single-shot done, starting full-paper-cycle -----"

"$PYTHON_BIN" tae.py full-paper-cycle
FULL_PAPER_CYCLE_EXIT=$?

if [ "$FULL_PAPER_CYCLE_EXIT" -eq 0 ]; then
    mkdir -p "$SCRIPT_DIR/runtime_outputs/hourly_refresh"
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$SCRIPT_DIR/runtime_outputs/hourly_refresh/last_success.txt"
fi

echo "----- full-paper-cycle done, starting parallel-paper (V1/V2/V3) run-once -----"
# No parallel-paper daemon/autostart exists in this checkout (module
# tae_parallel_paper_autostart.py is missing — parallel-paper-health/-start
# depend on it and are currently broken). Rather than rebuilding that
# subsystem, V1/V2/V3 piggyback on this already-hardened hourly job
# (RunAtLoad + pmset wakeorpoweron, fixed 2026-08-23) for their cadence.
# Non-fatal: a parallel-paper failure must not block the main heartbeat
# above, which existing tooling (tae_daily_check.sh) already keys off.
"$PYTHON_BIN" tae.py parallel-paper-run-once
PARALLEL_PAPER_EXIT=$?
if [ "$PARALLEL_PAPER_EXIT" -eq 0 ]; then
    mkdir -p "$SCRIPT_DIR/runtime_outputs/parallel_paper"
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$SCRIPT_DIR/runtime_outputs/parallel_paper/hourly_trigger_last_success.txt"
else
    echo "WARNING: parallel-paper-run-once exited $PARALLEL_PAPER_EXIT"
fi

echo "----- V1/V2/V3 done, starting exp_short_margin (short+margin) run-once -----"
# Self-contained isolated arm (tae_parallel_paper_short_margin.py) — does not
# touch V1/V2/V3's portfolios or journals. Non-fatal, same reasoning as above:
# a failure here must not block the V1/V2/V3 heartbeat that already exists.
"$PYTHON_BIN" tae.py parallel-paper-run-short-margin-once
SHORT_MARGIN_EXIT=$?
if [ "$SHORT_MARGIN_EXIT" -eq 0 ]; then
    mkdir -p "$SCRIPT_DIR/runtime_outputs/parallel_paper/exp_short_margin"
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$SCRIPT_DIR/runtime_outputs/parallel_paper/exp_short_margin/hourly_trigger_last_success.txt"
else
    echo "WARNING: parallel-paper-run-short-margin-once exited $SHORT_MARGIN_EXIT"
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') hourly refresh end ====="
