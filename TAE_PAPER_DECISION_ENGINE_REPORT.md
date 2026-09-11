# TAE Paper Decision Engine Report

**Generated:** 2026-09-11T14:01:56+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE — NO_EXECUTION
**Live promotion allowed:** false

> **PAPER_ONLY explicit decisions — no broker execution, no live promotion, no live file changes**

## Executive summary

- Decisions generated: **98**
- **BUY_PAPER**: 19
- **HOLD_PAPER**: 20
- **PROTECT_PAPER**: 1
- **SELL_PAPER**: 6
- **SKIP_PAPER**: 52

## Decision table

| ticker | action | confidence | risk | profit Δ | cap eff Δ | switch | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| FTNT | BUY_PAPER | 0.593 | 0.0 | 17.31 | -0.57 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| ALV.DE | BUY_PAPER | 0.374 | 0.0 | 17.31 | -0.57 | switch=yes | monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY  |
| IBM | BUY_PAPER | 0.344 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| MET | BUY_PAPER | 0.344 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| ORCL | BUY_PAPER | 0.344 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| TER | BUY_PAPER | 0.344 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| AIG | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| ALL | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| AZN.L | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| BAC | BUY_PAPER | 0.25 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| CB | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| ENTG | BUY_PAPER | 0.25 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| GS | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| MRVL | BUY_PAPER | 0.25 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| PLTR | BUY_PAPER | 0.25 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| SAP.DE | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| STT | BUY_PAPER | 0.25 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| V | BUY_PAPER | 0.25 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| WDAY | BUY_PAPER | 0.25 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY; limited capital hint from accounting snap |
| HSBA.L | SELL_PAPER | 0.95 | 100.0 | 37.38 | 3.6 | switch=no | PROFIT_TRAILING_EXIT_DRAWDOWN_2_PERCENT: mark=1555.0 peak=16 |
| ANET | SELL_PAPER | 0.906 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY score=100.0 ag |
| CRWD | SELL_PAPER | 0.896 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY score=100.0 ag |
| JPM | SELL_PAPER | 0.853 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY score=100.0 ag |
| BP.L | SELL_PAPER | 0.817 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY score=100.0 ag |
| AMD | SELL_PAPER | 0.805 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY age=0.0h (held |

## Decision state / switch summary

- Switch authorized: **90**
- Switch blocked (PDE gate): **7**
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
