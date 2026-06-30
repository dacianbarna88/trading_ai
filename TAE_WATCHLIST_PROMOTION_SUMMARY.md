# TAE Watchlist Promotion Summary

**Status:** APPLIED
**Generated:** 2026-06-30T10:11:05.175993+00:00
**Safety:** GOVERNED_CONFIG_CHANGE | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE | WATCHLIST_APPEND_ONLY

## Counts

- Old count: **15**
- New count: **25**
- Additions: **10**
- Skipped duplicates: **0**

## Source proposal

- File: `tae_watchlist_proposal.json`
- Generated: 2026-06-30T10:08:08.008037+00:00
- Global data sufficient: True

## Additions

- DIA
- LLY
- ABBV
- AMAT
- MRK
- MU
- PG
- PM
- GE
- HD

## Backup & rollback

- Backup path: `backups/watchlist_20260630_101105.txt`
- Rollback: `cp backups/watchlist_20260630_101105.txt watchlist.txt`

## Restart

- Restart needed: **no**
- Note: live_bot.py calls load_watchlist() each signal cycle (~60s); new tickers are included on the next cycle without restart. Optional restart only if bot process is stuck or operator wants immediate rescan.

## Governance

- Existing tickers preserved in original order
- Append-only — no removals
- live_bot.py not modified
