# TAE Paper Decision Engine Report

**Generated:** 2026-09-03T13:02:36+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE — NO_EXECUTION
**Live promotion allowed:** false

> **PAPER_ONLY explicit decisions — no broker execution, no live promotion, no live file changes**

## Executive summary

- Decisions generated: **98**
- **BUY_PAPER**: 39
- **HOLD_PAPER**: 10
- **PROTECT_PAPER**: 1
- **SKIP_PAPER**: 48

## Decision table

| ticker | action | confidence | risk | profit Δ | cap eff Δ | switch | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| PM | BUY_PAPER | 0.946 | 16.48 | 15.69 | -0.61 | switch=yes | healthy winner lifecycle=EARLY_WINNER; signal=STRONG BUY age |
| LLY | BUY_PAPER | 0.727 | 19.52 | 15.69 | -0.61 | switch=yes | healthy winner lifecycle=EARLY_WINNER; top_growth_candidate  |
| ADBE | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| HPQ | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| ICE | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| MCO | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| NOW | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| QRVO | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| SNPS | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| SPGI | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| STT | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| SWKS | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| WFC | BUY_PAPER | 0.717 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| HSBA.L | BUY_PAPER | 0.714 | 100.0 | 37.38 | 3.6 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| BP.L | BUY_PAPER | 0.66 | 0.0 | 15.69 | -0.61 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY age=0.0h (held |
| CRWD | BUY_PAPER | 0.545 | 0.0 | 15.69 | -0.61 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| DELL | BUY_PAPER | 0.545 | 0.0 | 15.69 | -0.61 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| ALL | BUY_PAPER | 0.543 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| BAC | BUY_PAPER | 0.543 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| CME | BUY_PAPER | 0.543 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| COF | BUY_PAPER | 0.543 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| INTU | BUY_PAPER | 0.543 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| MA | BUY_PAPER | 0.543 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| MET | BUY_PAPER | 0.543 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| MSFT | BUY_PAPER | 0.543 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |

## Decision state / switch summary

- Switch authorized: **98**
- Switch blocked (PDE gate): **0**
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
