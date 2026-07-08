# TAE Paper Decision Engine Report

**Generated:** 2026-07-08T19:30:07+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE — NO_EXECUTION
**Live promotion allowed:** false

> **PAPER_ONLY explicit decisions — no broker execution, no live promotion, no live file changes**

## Executive summary

- Decisions generated: **25**
- **BUY_PAPER**: 2
- **HOLD_PAPER**: 7
- **PROTECT_PAPER**: 3
- **SELL_PAPER**: 2
- **SKIP_PAPER**: 11

## Decision table

| ticker | action | confidence | risk | profit Δ | cap eff Δ | switch | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| HSBA.L | BUY_PAPER | 0.275 | 100.0 | 37.38 | 3.6 | switch=yes | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| MU | BUY_PAPER | 0.275 | 100.0 | 35.9 | 2.9 | switch=yes | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| AMAT | SELL_PAPER | 0.95 | 100.0 | 35.25 | 2.9 | switch=no | HARD RISK override (HARD_STOP_LOSS_-3): -3.50% loss → SELL_P |
| HD | SELL_PAPER | 0.5 | 0.0 | 12.54 | -0.0 | switch=yes | low capital_efficiency=0.0; knowledge base rules: MISSED_PRO |
| AAPL | PROTECT_PAPER | 0.931 | 21.22 | 5.43 | -0.51 | switch=yes | protection posture/signal=/TRAILING_PROTECTION_SHADOW; monit |
| LLY | PROTECT_PAPER | 0.921 | 43.32 | 4.96 | 2.58 | switch=yes | protection posture/signal=TRAIL_SHADOW/; monitor strategy=HO |
| MC.PA | PROTECT_PAPER | 0.461 | 21.28 | 3.31 | -0.78 | switch=yes | monitor strategy=HOLD_AND_MONITOR_SHADOW; knowledge base rul |
| AIR.PA | HOLD_PAPER | 0.753 | 0.0 | 0.0 | 0.0 | switch=no | low capital_efficiency=0.0; knowledge base rules: MISSED_PRO |
| DIA | HOLD_PAPER | 0.753 | 0.0 | 0.0 | 0.0 | switch=no | low capital_efficiency=0.0; knowledge base rules: MISSED_PRO |
| GE | HOLD_PAPER | 0.753 | 0.0 | 0.0 | 0.0 | switch=no | low capital_efficiency=0.0; knowledge base rules: MISSED_PRO |
| SPY | HOLD_PAPER | 0.675 | 18.7 | 4.37 | -1.84 | switch=yes | healthy winner lifecycle=EARLY_WINNER; horizon: candidate al |
| PM | HOLD_PAPER | 0.618 | 16.68 | 4.27 | -1.97 | switch=yes | healthy winner lifecycle=EARLY_WINNER; knowledge base rules: |
| PG | HOLD_PAPER | 0.616 | 11.33 | 11.41 | -0.98 | switch=yes | healthy winner lifecycle=SURVIVED; horizon: candidate alignm |
| MRK | HOLD_PAPER | 0.593 | 10.37 | 0.32 | -1.92 | switch=yes | healthy winner lifecycle=SURVIVED; horizon: candidate alignm |
| QQQ | SKIP_PAPER | 0.331 | 80.05 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; horizon BUY ga |
| ABBV | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| ALV.DE | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| AZN.L | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| BP.L | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| MSFT | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| NVDA | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| SAP.DE | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| SHEL.L | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| SIE.DE | SKIP_PAPER | 0.25 | 19.03 | 18.45 | -0.51 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |
| ULVR.L | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | switch=yes | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; knowledge base |

## Decision state / switch summary

- Switch authorized: **21**
- Switch blocked (PDE gate): **3**
- Active decisions loaded: **True**

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
