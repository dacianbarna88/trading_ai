# TAE Paper Decision Engine Report

**Generated:** 2026-09-12T15:02:08+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE — NO_EXECUTION
**Live promotion allowed:** false

> **PAPER_ONLY explicit decisions — no broker execution, no live promotion, no live file changes**

## Executive summary

- Decisions generated: **98**
- **BUY_PAPER**: 18
- **HOLD_PAPER**: 18
- **PROTECT_PAPER**: 1
- **SELL_PAPER**: 4
- **SKIP_PAPER**: 57

## Decision table

| ticker | action | confidence | risk | profit Δ | cap eff Δ | switch | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| CRWD | BUY_PAPER | 0.773 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY score=100.0 ag |
| JPM | BUY_PAPER | 0.773 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY score=100.0 ag |
| ALV.DE | BUY_PAPER | 0.472 | 0.0 | 17.31 | -0.57 | switch=yes | monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY  |
| NVDA | BUY_PAPER | 0.465 | 0.0 | 15.0 | 5.0 | switch=yes | monitor strategy=HOLD_AND_MONITOR_SHADOW; signal=STRONG BUY  |
| ADI | BUY_PAPER | 0.355 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| BAC | BUY_PAPER | 0.355 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| IBM | BUY_PAPER | 0.355 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| MET | BUY_PAPER | 0.355 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| ORCL | BUY_PAPER | 0.355 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| TER | BUY_PAPER | 0.355 | 0.0 | 15.0 | 5.0 | switch=yes | signal=STRONG BUY score=100.0; limited capital hint from acc |
| AIG | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| AIR.PA | BUY_PAPER | 0.25 | 10.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| ALL | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| CB | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| FTNT | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| GS | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| INTU | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| SAP.DE | BUY_PAPER | 0.25 | 0.0 | 17.31 | -0.57 | switch=yes | limited capital hint from accounting snapshot; live promotio |
| ANET | SELL_PAPER | 0.95 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY score=100.0 ag |
| HSBA.L | SELL_PAPER | 0.95 | 100.0 | 37.38 | 3.6 | switch=no | PROFIT_TRAILING_EXIT_DRAWDOWN_2_PERCENT: mark=1552.599976 pe |
| BP.L | SELL_PAPER | 0.794 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY score=100.0 ag |
| AMD | SELL_PAPER | 0.656 | 0.0 | 17.31 | -0.57 | switch=yes | low capital_efficiency=0.0; signal=STRONG BUY age=0.0h (held |
| QQQ | PROTECT_PAPER | 0.568 | 70.05 | 1.97 | -1.0 | switch=yes | weak lifecycle=WEAKENING; GII strategy=PROTECT_PROFIT_SHADOW |
| DELL | HOLD_PAPER | 0.95 | 0.0 | 17.31 | -0.57 | switch=yes | profit trailing: PROFIT_TRAILING_HOLD; low capital_efficienc |
| HPQ | HOLD_PAPER | 0.95 | 0.0 | 0.0 | 0.0 | switch=yes | profit trailing: PROFIT_TRAILING_HOLD; low capital_efficienc |

## Decision state / switch summary

- Switch authorized: **91**
- Switch blocked (PDE gate): **6**
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
