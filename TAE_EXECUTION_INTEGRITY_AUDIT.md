# TAE Execution Integrity Audit

**Generated:** 2026-06-29T22:28:19.903904+00:00  
**Mode:** ACCOUNTING_INTEGRITY_READ_ONLY  
**Live trading impact:** NONE

## Root cause

update_portfolio_prices() in live_bot.py rewrites PnL on ALL rows including SELL, using live Current_Price vs row Price*Shares instead of freezing realized PnL at sell time. sell_position() computes correct realized PnL at execution; subsequent mark-to-market pass corrupts it.

## Fix (future rows)

update_portfolio_prices skips SELL/DEPOSIT/CASH and closed BUY rows

## Summary

- Total SELL rows: 26
- SELL OK: 0
- SELL mismatched: 26
- Reported realized PnL: -700.3663
- Corrected realized PnL: 267.7422
- Delta: -968.1085
- Status: **MISMATCH_DETECTED**
- Recommended next action: PORTFOLIO_HISTORICAL_REWRITE_OPTIONAL

## Biggest mismatches

- **GS** (2026-06-17 17:29:43): reported -903.8957 vs expected 547.9904 — MISMATCH_REASON_PNL
  - Reason: PROFIT +5.48%
- **AAPL** (2026-06-25 18:19:50): reported 40.3048 vs expected -189.2578 — MISMATCH_REASON_PNL
  - Reason: STOP LOSS -8.24%
- **ULVR.L** (2026-06-26 12:03:01): reported -17.3734 vs expected 120.9427 — MISMATCH_REASON_PNL
  - Reason: TAKE PROFIT SIGNAL
- **SIE.DE** (2026-06-24 16:11:11): reported 7.8481 vs expected -93.6152 — MISMATCH_REASON_PNL
  - Reason: STOP LOSS -3.02%
- **PANW** (2026-06-17 17:29:43): reported 182.059 vs expected 90.6923 — POSSIBLE_ACCOUNTING_BUG
  - Reason: PROFIT +10.01%
- **MRK** (2026-06-15 10:11:31): reported 85.4039 vs expected 0.0 — POSSIBLE_ACCOUNTING_BUG
  - Reason: EXTRA SLOT REDUCE SIMULATION
- **UNH** (2026-06-15 10:11:31): reported 55.4086 vs expected 0.0 — POSSIBLE_ACCOUNTING_BUG
  - Reason: EXTRA SLOT REDUCE SIMULATION
- **AMD** (2026-06-09 03:42:04): reported 105.4089 vs expected 51.3536 — POSSIBLE_ACCOUNTING_BUG
  - Reason: PROFIT +5.14%
- **ADBE** (2026-06-09 19:04:45): reported -114.7791 vs expected -64.2302 — POSSIBLE_ACCOUNTING_BUG
  - Reason: STOP LOSS -6.42%
- **ORCL** (2026-06-11 16:31:01): reported -138.7037 vs expected -105.4381 — POSSIBLE_ACCOUNTING_BUG
  - Reason: STOP LOSS -11.64%

## All SELL audits

- AMD | POSSIBLE_ACCOUNTING_BUG | reported 105.4089 | expected 51.3536 | PROFIT +5.14%
- NOW | POSSIBLE_ACCOUNTING_BUG | reported -46.7832 | expected -57.2691 | STOP LOSS -5.73%
- AAPL | POSSIBLE_ACCOUNTING_BUG | reported -30.9753 | expected -52.3195 | STOP LOSS -5.23%
- CRM | POSSIBLE_ACCOUNTING_BUG | reported -81.4895 | expected -57.6695 | STOP LOSS -5.77%
- ADBE | POSSIBLE_ACCOUNTING_BUG | reported -114.7791 | expected -64.2302 | STOP LOSS -6.42%
- ORCL | POSSIBLE_ACCOUNTING_BUG | reported -138.7037 | expected -105.4381 | STOP LOSS -11.64%
- MSFT | POSSIBLE_ACCOUNTING_BUG | reported -43.368 | expected -72.072 | STOP LOSS -7.21%
- SPY | POSSIBLE_ACCOUNTING_BUG | reported 4.6775 | expected 0.0 | GLOBAL REDUCE SIMULATION
- QQQ | POSSIBLE_ACCOUNTING_BUG | reported 26.9761 | expected 0.0 | GLOBAL REDUCE SIMULATION
- UNH | POSSIBLE_ACCOUNTING_BUG | reported 55.4086 | expected 0.0 | EXTRA SLOT REDUCE SIMULATION
- DIA | POSSIBLE_ACCOUNTING_BUG | reported 21.4194 | expected 0.0 | EXTRA SLOT REDUCE SIMULATION
- MRK | POSSIBLE_ACCOUNTING_BUG | reported 85.4039 | expected 0.0 | EXTRA SLOT REDUCE SIMULATION
- CRWD | POSSIBLE_ACCOUNTING_BUG | reported 84.5514 | expected 79.8126 | PROFIT +8.81%
- AMD | POSSIBLE_ACCOUNTING_BUG | reported 11.5989 | expected 37.1385 | PROFIT +11.96%
- PANW | POSSIBLE_ACCOUNTING_BUG | reported 182.059 | expected 90.6923 | PROFIT +10.01%
- CAT | POSSIBLE_ACCOUNTING_BUG | reported 21.9398 | expected 20.1305 | PROFIT +6.51%
- GS | MISMATCH_REASON_PNL | reported -903.8957 | expected 547.9904 | PROFIT +5.48%
- IBM | POSSIBLE_ACCOUNTING_BUG | reported 0.0014 | expected -0.0008 | STOP LOSS -3.00%
- INTC | POSSIBLE_ACCOUNTING_BUG | reported 0.0004 | expected 0.0015 | PROFIT +6.07%
- BRK-B | POSSIBLE_ACCOUNTING_BUG | reported 1.8092 | expected 3.758 | TAKE PROFIT SIGNAL
- SIE.DE | MISMATCH_REASON_PNL | reported 7.8481 | expected -93.6152 | STOP LOSS -3.02%
- V | POSSIBLE_ACCOUNTING_BUG | reported 23.6951 | expected 38.4597 | TAKE PROFIT SIGNAL
- AAPL | MISMATCH_REASON_PNL | reported 40.3048 | expected -189.2578 | STOP LOSS -8.24%
- ULVR.L | MISMATCH_REASON_PNL | reported -17.3734 | expected 120.9427 | TAKE PROFIT SIGNAL
- CSCO | MISMATCH_REASON_PNL | reported 3.8989 | expected -13.2766 | STOP LOSS -4.29%
- HSBA.L | MISMATCH_REASON_PNL | reported 0.0002 | expected -17.3888 | TAKE PROFIT SIGNAL
