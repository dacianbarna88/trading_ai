# TAE Portfolio Reconciliation

**Generated:** 2026-06-29T23:05:31.875435+00:00  
**Mode:** READ_ONLY_RECONCILIATION  
**Live trading impact:** NONE

## Summary

- Total SELL rows: 26
- SELL OK: 0
- SELL mismatched: 26
- Total reported realized PnL: -700.3663
- Corrected realized PnL: 267.7422
- Delta: -968.1085
- Recommended next action: PORTFOLIO_HISTORICAL_REWRITE_OPTIONAL

## Root cause

update_portfolio_prices() in live_bot.py rewrites PnL on ALL rows including SELL, using live Current_Price vs row Price*Shares instead of freezing realized PnL at sell time. sell_position() computes correct realized PnL at execution; subsequent mark-to-market pass corrupts it.
