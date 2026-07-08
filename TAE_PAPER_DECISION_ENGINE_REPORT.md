# TAE Paper Decision Engine Report

**Generated:** 2026-07-08T15:51:02+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE — NO_EXECUTION
**Live promotion allowed:** false

> **PAPER_ONLY explicit decisions — no broker execution, no live promotion, no live file changes**

## Executive summary

- Decisions generated: **25**
- **HOLD_PAPER**: 4
- **PROTECT_PAPER**: 3
- **SELL_PAPER**: 1
- **SKIP_PAPER**: 17

## Decision table

| ticker | action | confidence | risk | profit Δ | cap eff Δ | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| QQQ | SELL_PAPER | 0.925 | 80.05 | 0.79 | 0.64 | HARD RISK override (HARD_STOP_LOSS_-3): -3.21% loss → SELL_P |
| AAPL | PROTECT_PAPER | 0.867 | 21.22 | 5.43 | -0.51 | protection posture/signal=/TRAILING_PROTECTION_SHADOW; monit |
| LLY | PROTECT_PAPER | 0.856 | 43.32 | 4.96 | 2.58 | protection posture/signal=TRAIL_SHADOW/; monitor strategy=HO |
| MC.PA | PROTECT_PAPER | 0.398 | 21.28 | 3.31 | -0.78 | monitor strategy=HOLD_AND_MONITOR_SHADOW; knowledge base rul |
| SPY | HOLD_PAPER | 0.673 | 18.7 | 4.37 | -1.84 | healthy winner lifecycle=EARLY_WINNER; horizon: candidate al |
| PM | HOLD_PAPER | 0.615 | 16.68 | 4.27 | -1.97 | healthy winner lifecycle=EARLY_WINNER; knowledge base rules: |
| PG | HOLD_PAPER | 0.614 | 11.33 | 11.41 | -0.98 | healthy winner lifecycle=SURVIVED; horizon: candidate alignm |
| MRK | HOLD_PAPER | 0.59 | 10.37 | 0.32 | -1.92 | healthy winner lifecycle=SURVIVED; horizon: candidate alignm |
| AMAT | SKIP_PAPER | 0.356 | 100.0 | 35.25 | 2.9 | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| HSBA.L | SKIP_PAPER | 0.349 | 100.0 | 37.38 | 3.6 | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| HD | SKIP_PAPER | 0.344 | 0.0 | 12.54 | -0.0 | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| MU | SKIP_PAPER | 0.344 | 100.0 | 35.9 | 2.9 | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| SIE.DE | SKIP_PAPER | 0.344 | 19.03 | 18.45 | -0.51 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| ABBV | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| AIR.PA | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | signal=STRONG BUY score=100.0; policy=HIGH_RISK/CAPITAL_PRES |
| ALV.DE | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| AZN.L | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| BP.L | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| DIA | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| GE | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | signal=STRONG BUY score=100.0; policy=HIGH_RISK/CAPITAL_PRES |
| MSFT | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| NVDA | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| SAP.DE | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| SHEL.L | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| ULVR.L | SKIP_PAPER | 0.332 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |

## Closed intelligence loop

- Consumes: learning-to-profit hypotheses + experiment results
- Consumes: GII, PPG, APPE, profit protection, DPE adaptive/evaluation
- Consumes: portfolio.csv + live_signals.csv (read-only)
- Produces explicit PAPER BUY/SELL/HOLD/REDUCE/PROTECT/ROTATE/SKIP decisions
- Applies hypothesis validation/rejection rules and protection validation scoring
- Applies multi-horizon context (7D/1M/1Y/2Y/5Y/10Y/20Y) from existing SSOT artifacts

## Safety confirmation

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_LIVE_CHANGE | ✅ |
| NO_EXECUTION | ✅ |
| live_promotion_allowed | **false** |
| portfolio.csv modified | **false** |
| live_bot.py modified | **false** |
