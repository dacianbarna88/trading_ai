#!/bin/bash
# One line per minute: lid, power source, battery, display, SleepDisabled,
# keepawake process. Pure diagnostics -- changes nothing on the Mac.
#
# Why: on 2026-10-29 the Mac slept at 21:03 (pmset logged 'Clamshell Sleep',
# AC -> battery within 15 s) although `caffeinate -i -s` was running, and it
# was unclear what triggered it. launchd does not fire while the Mac sleeps,
# so the last line before a gap is the state right before sleep, and the
# first run after the gap appends pmset's own Sleep/Wake lines for the gap.
#
# Read it with: tail -n 40 ~/Library/Logs/tradingai-sleepdiag.log
set -u
LOG="$HOME/Library/Logs/tradingai-sleepdiag.log"
LAST="$HOME/Library/Logs/.tradingai-sleepdiag.last"
GAP_SECS=150

now=$(date +%s)
lid=$(ioreg -r -k AppleClamshellState -d 4 | awk -F'= ' '/"AppleClamshellState"/{print $2; exit}')
ps_out=$(pmset -g ps)
src=$(printf '%s\n' "$ps_out" | sed -n "s/.*drawing from '\(.*\)'.*/\1/p")
batt=$(printf '%s\n' "$ps_out" | grep -o '[0-9]*%' | head -n 1)
disp=$(pmset -g powerstate IODisplayWrangler | awk '/^IODisplayWrangler/{print $2}')
sleepdisabled=$(pmset -g | awk '/SleepDisabled/{print $2}')
caf=$(pgrep -f "caffeinate -i -s" | head -n 1)

if [ -f "$LAST" ]; then
  prev=$(cat "$LAST")
  if [ $((now - prev)) -gt "$GAP_SECS" ]; then
    from=$(date -r "$prev" '+%Y-%m-%d %H:%M')
    {
      echo "$(date '+%Y-%m-%d %H:%M:%S') GAP $((now - prev))s (no run since $from) -- pmset events in the gap:"
      pmset -g log | grep -E '^[0-9-]+ [0-9:]+ [+-][0-9]{4} (Sleep|Wake|DarkWake) |Notification[[:space:]]+Display is' \
        | awk -v from="$from" '{ if (substr($0, 1, 16) >= from) print "    " substr($0, 1, 220) }'
    } >> "$LOG"
  fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') lid_closed=${lid:-?} power=${src:-?} batt=${batt:-?} display_state=${disp:-?} SleepDisabled=${sleepdisabled:-0} keepawake_pid=${caf:-NONE}" >> "$LOG"
echo "$now" > "$LAST"

# Keep the log small: ~1 line/minute is ~3 MB/month.
if [ "$(wc -c < "$LOG")" -gt 5000000 ]; then
  tail -n 20000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
