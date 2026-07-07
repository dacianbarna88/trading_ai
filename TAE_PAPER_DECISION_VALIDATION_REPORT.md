# TAE Paper Decision Validation Report

**Generated:** 2026-07-07T13:46:14+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE
**Live promotion allowed:** false

> **PAPER_ONLY simulated validation — no broker execution**

## Executive summary

- Decisions consumed (raw): **50**
- Unique decisions validated: **25**
- PROMISING: **2**
- CONTINUE_TESTING: **5**
- NEEDS_MORE_DATA: **18**
- REJECT: **0**

## Ranked validated decisions (unique)

| rank | ticker | action | verdict | profit Δ | risk Δ | cap eff Δ | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | AMAT | PROTECT_PAPER | PROMISING | 41.09 | -0.14 | -0.5 | PROMISING: PROTECT_PAPER on AMAT simulates +$41.09 profit with riskΔ=-0.1400 and |
| 2 | HSBA.L | SELL_PAPER | PROMISING | 37.38 | -0.08 | 4.5 | PROMISING: SELL_PAPER on HSBA.L simulates +$37.38 profit with riskΔ=-0.0800 and  |
| 3 | LLY | PROTECT_PAPER | CONTINUE_TESTING | 8.63 | -0.14 | -0.65 | CONTINUE: PROTECT_PAPER on LLY shows modest simulated gain +$8.63 (riskΔ=-0.1400 |
| 4 | SPY | HOLD_PAPER | CONTINUE_TESTING | 4.37 | 0.02 | -1.84 | CONTINUE: HOLD_PAPER on SPY shows modest simulated gain +$4.37 (riskΔ=0.0200, ca |
| 5 | PM | HOLD_PAPER | CONTINUE_TESTING | 4.27 | 0.02 | -1.97 | CONTINUE: HOLD_PAPER on PM shows modest simulated gain +$4.27 (riskΔ=0.0200, cap |
| 6 | PG | HOLD_PAPER | CONTINUE_TESTING | 4.2 | 0.02 | -0.98 | CONTINUE: HOLD_PAPER on PG shows modest simulated gain +$4.20 (riskΔ=0.0200, cap |
| 7 | AZN.L | SELL_PAPER | CONTINUE_TESTING | 0.0 | -0.08 | 5.0 | CONTINUE: SELL_PAPER on AZN.L shows modest simulated gain +$0.00 (riskΔ=-0.0800, |
| 8 | MU | PROTECT_PAPER | NEEDS_MORE_DATA | 35.9 | -0.14 | -0.5 | NEEDS_MORE_DATA: PROTECT_PAPER on MU — missing: confidence 0.38 below 0.40 thres |
| 9 | MRK | BUY_PAPER | NEEDS_MORE_DATA | 12.83 | 0.04 | 3.0 | NEEDS_MORE_DATA: BUY_PAPER on MRK — missing: confidence 0.25 below 0.40 threshol |
| 10 | SIE.DE | HOLD_PAPER | NEEDS_MORE_DATA | 8.91 | 0.02 | -0.51 | NEEDS_MORE_DATA: HOLD_PAPER on SIE.DE — missing: confidence 0.30 below 0.40 thre |
| 11 | AAPL | HOLD_PAPER | NEEDS_MORE_DATA | 5.59 | 0.02 | -0.51 | NEEDS_MORE_DATA: HOLD_PAPER on AAPL — missing: confidence 0.30 below 0.40 thresh |
| 12 | QQQ | PROTECT_PAPER | NEEDS_MORE_DATA | 1.97 | -0.15 | -1.0 | NEEDS_MORE_DATA: PROTECT_PAPER on QQQ — missing: confidence 0.34 below 0.40 thre |
| 13 | MC.PA | HOLD_PAPER | NEEDS_MORE_DATA | 0.84 | 0.03 | 0.0 | NEEDS_MORE_DATA: HOLD_PAPER on MC.PA — missing: confidence 0.28 below 0.40 thres |
| 14 | ABBV | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on ABBV — missing: action was SKIP — need stronger G |
| 15 | AIR.PA | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on AIR.PA — missing: action was SKIP — need stronger |
| 16 | ALV.DE | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on ALV.DE — missing: action was SKIP — need stronger |
| 17 | BP.L | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on BP.L — missing: action was SKIP — need stronger G |
| 18 | DIA | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on DIA — missing: action was SKIP — need stronger GI |
| 19 | GE | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on GE — missing: action was SKIP — need stronger GII |
| 20 | HD | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on HD — missing: action was SKIP — need stronger GII |
| 21 | MSFT | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on MSFT — missing: action was SKIP — need stronger G |
| 22 | NVDA | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on NVDA — missing: action was SKIP — need stronger G |
| 23 | SAP.DE | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on SAP.DE — missing: action was SKIP — need stronger |
| 24 | SHEL.L | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on SHEL.L — missing: action was SKIP — need stronger |
| 25 | ULVR.L | SKIP_PAPER | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 | NEEDS_MORE_DATA: SKIP_PAPER on ULVR.L — missing: action was SKIP — need stronger |

## Safety confirmation

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_LIVE_CHANGE | ✅ |
| live_promotion_allowed | **false** |
