# TAE Maturity Timestamp Audit

**Mode:** READ-ONLY · NO CODE CHANGES · NO COMMIT  
**Date:** 2026-07-24  
**Subject:** Why `next_maturity_timestamp = 2026-08-03T15:30:00Z`

## Verdict

`MATURITY_TIMESTAMP_CORRECT_WITH_LIMITATIONS`

## Earliest outcomes (drive the reported next maturity)

Four UK LSE names share the earliest due:

| decision_id | ticker | market | decision_timestamp | horizon | maturity_due_at |
|-------------|--------|--------|--------------------|---------|-----------------|
| PDEC-AZN.L-0006 | AZN.L | UK | 2026-07-23T22:35:36Z | 7D | 2026-08-03T15:30:00Z |
| PDEC-BP.L-0007 | BP.L | UK | 2026-07-23T22:35:36Z | 7D | 2026-08-03T15:30:00Z |
| PDEC-HSBA.L-0011 | HSBA.L | UK | 2026-07-23T22:35:36Z | 7D | 2026-08-03T15:30:00Z |
| PDEC-SHEL.L-0022 | SHEL.L | UK | 2026-07-23T22:35:36Z | 7D | 2026-08-03T15:30:00Z |

`next_maturity_timestamp` = `min(maturity_due_at)` over non-terminal pending records  
(`next_maturity_timestamp()` in `tae_learning_economic_attribution_engine.py`).

## Horizon source

- File: `tae_learning_economic_attribution_engine.py`
- Constant: `DEFAULT_HORIZON_TRADING_DAYS = {"1D": 1, "7D": 7, "30D": 21}`
- Function: `horizon_trading_days("7D")` → **7**
- Unit: **trading days (weekdays Mon–Fri)**, not calendar days
- Row field: `outcome_horizon` / pending `horizon` = `"7D"` (set in `build_impact_rows` as hardcode `"7D"`)
- Call path: `pending_record_from_ledger_row` → `add_trading_days(ts, horizon_trading_days(horizon), market=...)`

## Calculation (AZN.L / UK)

1. `decision_timestamp` = `2026-07-23T22:35:36Z` → London `2026-07-23T23:35:36+01:00` (Thursday)
2. Advance **7 weekdays** in market TZ (Sat/Sun skipped): Fri 24, Mon 27, Tue 28, Wed 29, Thu 30, Fri 31, **Mon Aug 3**
3. Holidays: **not applied** (weekday-only; docstring + `market_hours.regular_session_open_close` state holidays not in SSOT)
4. Session close from `markets/market_config.py` UK: `close_hour=16`, `close_minute=30` Europe/London
5. Convert to UTC: `2026-08-03T16:30:00+01:00` (BST) → **`2026-08-03T15:30:00Z`**

## Why 15:30 UTC

Not market open. Not a hardcoded date. It is **UK regular session close** (16:30 London) expressed in UTC under British Summer Time.

## Per-market results (same decision time)

| market | earliest due | clock meaning |
|--------|--------------|---------------|
| UK (4) | 2026-08-03T15:30:00Z | 16:30 London |
| US (9) | 2026-08-03T20:00:00Z | 16:00 US/Eastern (EDT) |
| EU (2) | 2026-08-04T15:30:00Z | 17:30 Berlin; local decision lands on Fri 00:35 so count shifts +1 day |

## Hardcoded or derived

`DERIVED` — no source string `2026-08-03`; monitor/status only echo the computed min.

## Limitations

- Weekday-only, not a real exchange holiday calendar
- Decision local date can shift EU vs UK/US for late-UTC stamps
- Horizon label `7D` maps to 7 weekdays by constant, not bars/hours

## Distinct maturities

- Earliest: `2026-08-03T15:30:00Z`
- Latest: `2026-08-04T15:30:00Z`
- Distinct timestamps: **3**
- On 2026-08-03 (any hour): **13** (4 UK @ 15:30Z + 9 US @ 20:00Z)
