#!/bin/bash
# Arms two one-time wakes for THIS evening, so the Mac is awake for the
# trading rebalance jobs (tae2 21:30, stocks 21:40) and the portfolio
# report (23:30) even if it's asleep.
#
# Why two separate wakes, 2 hours apart, instead of one: `pmset schedule
# wake` only wakes the machine once -- it does not keep it awake -- and
# nothing here guarantees it stays up for 2+ hours between the rebalance
# jobs and the report. Waking again shortly before 23:30 is simpler and
# more robust than trying to hold the machine awake the whole gap.
#
# Why this can't just be `pmset repeat`: macOS allows only one repeating
# wake/poweron pair, and betting_ai's jobs (com.bettingai.scanner 08:05,
# resolve-results 08:00, daily-report 09:00, capture-clv 10:00) already
# rely on the existing `wakepoweron at 9:59AM weekdays`. This script uses
# the one-time `pmset schedule wake` facility instead (a completely
# separate mechanism from `repeat`), re-armed daily by the LaunchDaemon
# that runs this script -- scheduled for 10:05am, 6 minutes after that
# same reliable 9:59 wake, so arming is itself reliable without adding a
# second repeat slot.
#
# Needs root (pmset schedule requires it) -- this script is meant to run
# via a LaunchDaemon (runs as root natively), not a per-user LaunchAgent.
set -u
TODAY=$(date '+%m/%d/%y')
LOG="/Users/book/trading_ai_restored/state/arm_evening_wake.log"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') arming evening wakes for $TODAY ====="
  /usr/bin/pmset schedule wake "$TODAY 21:25:00" "trading_ai rebalance wake"
  /usr/bin/pmset schedule wake "$TODAY 23:25:00" "trading_ai portfolio report wake"
  echo "exit $?"
} >> "$LOG" 2>&1
