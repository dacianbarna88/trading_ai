# TAE Non-Terminal Order Recovery Audit

**Generated:** 2026-07-14T01:12:31

## Root cause

fill_price_for_position consulted only accounting/decision snapshot; live_signals.csv and market-data layer were not used for new-entry BUY fills.

## Mark-price failure cases

### AIR.PA

- Live signal price: **0.0** @ None
- Resolved now: **195.899994** (FALLBACK_STALE, FRESH)
- Canonical open position: **True**
- Valid mark elsewhere: **True**
- Failure reason: resolved_now
- Skip orders: 1

### DIA

- Live signal price: **524.47** @ 2026-07-14 02:28:40
- Resolved now: **524.47** (live_signals.csv, FRESH)
- Canonical open position: **True**
- Valid mark elsewhere: **True**
- Failure reason: resolved_now
- Skip orders: 1

### GE

- Live signal price: **353.42** @ 2026-07-14 02:28:51
- Resolved now: **353.420013** (yfinance_download_5d, FRESH)
- Canonical open position: **True**
- Valid mark elsewhere: **True**
- Failure reason: resolved_now
- Skip orders: 1

### HD

- Live signal price: **337.11** @ 2026-07-14 02:28:53
- Resolved now: **337.109985** (yfinance_download_5d, FRESH)
- Canonical open position: **False**
- Valid mark elsewhere: **True**
- Failure reason: resolved_now
- Skip orders: 4

## Terminal vs non-terminal

- **Terminal:** EXECUTED, NO_CHANGE
- **Non-terminal:** BLOCKED_FAKE_PROFIT_RISK, SKIPPED_NO_MARK_PRICE, SKIPPED_NO_POSITION, SKIPPED_SWITCH_NOT_AUTHORIZED

