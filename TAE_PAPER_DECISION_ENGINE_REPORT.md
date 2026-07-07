# TAE Paper Decision Engine Report

**Generated:** 2026-07-07T11:32:09+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE — NO_EXECUTION
**Live promotion allowed:** false

> **PAPER_ONLY explicit decisions — no broker execution, no live promotion, no live file changes**

## Executive summary

- Decisions generated: **25**
- **HOLD_PAPER**: 7
- **PROTECT_PAPER**: 3
- **SELL_PAPER**: 2
- **SKIP_PAPER**: 13

## Decision table

| ticker | action | confidence | risk | profit Δ | cap eff Δ | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| HSBA.L | SELL_PAPER | 0.797 | 100.0 | 37.38 | 3.6 | low capital_efficiency=0.0; weak lifecycle=COLLAPSED; protec |
| QQQ | SELL_PAPER | 0.28 | 80.05 | 0.79 | 0.64 | weak lifecycle=WEAKENING; GII strategy=PROTECT_PROFIT_SHADOW |
| AMAT | PROTECT_PAPER | 0.706 | 100.0 | 35.25 | 2.9 | weak lifecycle=PROFIT_DECAY; protection posture/signal=PROTE |
| LLY | PROTECT_PAPER | 0.445 | 43.32 | 8.63 | -0.65 | protection posture/signal=TRAIL_SHADOW/NO_PROTECTION; monito |
| MU | PROTECT_PAPER | 0.306 | 100.0 | 35.9 | 2.9 | weak lifecycle=PROFIT_DECAY; GII strategy=TIGHTEN_TRAIL_SHAD |
| MRK | HOLD_PAPER | 0.52 | 10.37 | 10.33 | -0.96 | healthy winner lifecycle=SURVIVED; experiment LTB-PROT-MRK P |
| PM | HOLD_PAPER | 0.515 | 16.68 | 4.27 | -1.97 | healthy winner lifecycle=EARLY_WINNER; PAPER_LIFECYCLE_HOLD; |
| SPY | HOLD_PAPER | 0.511 | 18.7 | 4.37 | -1.84 | healthy winner lifecycle=EARLY_WINNER; PAPER_LIFECYCLE_HOLD; |
| PG | HOLD_PAPER | 0.51 | 11.33 | 4.2 | -0.98 | healthy winner lifecycle=SURVIVED; PAPER_TRAILING_PROTECT_TR |
| AAPL | HOLD_PAPER | 0.298 | 21.22 | 5.59 | -0.51 | monitor strategy=HOLD_AND_MONITOR_SHADOW; experiment LTB-PRO |
| SIE.DE | HOLD_PAPER | 0.298 | 19.03 | 8.91 | -0.51 | monitor strategy=HOLD_AND_MONITOR_SHADOW; experiment LTB-PRO |
| MC.PA | HOLD_PAPER | 0.28 | 21.28 | 0.84 | 0.0 | monitor strategy=HOLD_AND_MONITOR_SHADOW; experiment LTB-DPE |
| ABBV | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| AIR.PA | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| ALV.DE | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| AZN.L | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| BP.L | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| DIA | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| GE | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| HD | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | signal=STRONG BUY; policy=HIGH_RISK/CAPITAL_PRESERVATION_SHA |
| MSFT | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| NVDA | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| SAP.DE | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| SHEL.L | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |
| ULVR.L | SKIP_PAPER | 0.25 | 0.0 | 0.0 | 0.0 | policy=HIGH_RISK/CAPITAL_PRESERVATION_SHADOW; experiment LTB |

## Closed intelligence loop

- Consumes: learning-to-profit hypotheses + experiment results
- Consumes: GII, PPG, APPE, profit protection, DPE adaptive/evaluation
- Consumes: portfolio.csv + live_signals.csv (read-only)
- Produces explicit PAPER BUY/SELL/HOLD/REDUCE/PROTECT/ROTATE/SKIP decisions

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
