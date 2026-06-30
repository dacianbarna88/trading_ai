# TAE Independent Position Risk Fix Report

**Sprint:** Position risk monitor patch  
**Mode:** PAPER_ONLY | NO_BROKER  
**Generated:** 2026-06-30

## Problem (AAPL)

- Configured `STOP_LOSS_PCT = -3`
- AAPL exit on 2026-06-25 at 276.91 vs BUY 299.59 (~-7.57% actual, logged as -8.24%)
- Stop did not fire at -3% because `manage_portfolio()` only evaluates open positions when the ticker appears in `signals_df`
- When `yf.download()` fails, ticker is skipped in `generate_signals()` → no stop-loss evaluation that cycle

## Root Cause

1. **Signal-dependent risk path:** SELL/stop logic runs only inside the `signals_df` loop
2. **Market data gaps:** Repeated `possibly delisted; no price data found` for AAPL
3. **Stale avg_price:** `get_open_positions()` averaged all historical BUY rows, including closed lots (inflated loss %)

## Fix Applied

### `live_bot.py`

1. **`manage_position_risk_independent(portfolio, signals_df=None)`**
   - Iterates open positions via `get_open_positions()`
   - Fetches price via `get_latest_price()` only (no buy-price fallback for risk)
   - Logs `RISK DATA STALE pentru {ticker}: stop-loss not evaluated` when price missing
   - Executes SELL with `INDEPENDENT RISK STOP LOSS` / `INDEPENDENT RISK TAKE PROFIT` reasons

2. **`manage_portfolio()` integration**
   - Calls independent monitor at end, before `save_portfolio()` (safety net, no duplicate if already sold)

3. **`get_open_positions()` FIFO patch**
   - Cost basis computed only on net open shares (closed lots excluded)

### `tae_independent_position_risk_test.py`

- Stop-loss when AAPL absent from `signals_df` with mocked price 276.91
- Stale price (`None`) → no sell + DATA STALE log
- FIFO avg_price excludes closed lots

## Files Modified

- `live_bot.py`
- `tae_independent_position_risk_test.py` (new)
- `TAE_INDEPENDENT_POSITION_RISK_FIX_REPORT.md` (new)

## Validations

| Check | Result |
|---|---|
| `py_compile live_bot.py` | PASS |
| `tae_independent_position_risk_test.py` | PASS (3/3) |
| `py_compile` tae_unified_runtime / queue / proposal / audit | PASS |
| `tae_scanner_refresh.sh` | PASS (31/31) |
| `tae_full_ecosystem_review.sh` | PASS |

## Verdict

**PASS** — Independent position risk monitor closes the AAPL-class gap: open positions are evaluated even when `signals_df` omits a ticker due to yfinance failure. FIFO avg_price now reflects only net open cost basis (-7.57% at 276.91 vs 299.59, not inflated -8.24%).

## Safety Confirmations

- **BUY logic unchanged** — no edits to BUY gates, sizing, or `buy_position()`
- **Thresholds unchanged** — `STOP_LOSS_PCT=-3`, `TAKE_PROFIT_PCT=5`
- **PAPER_ONLY / NO_BROKER** — no broker integration added; existing paper portfolio CSV flow only
