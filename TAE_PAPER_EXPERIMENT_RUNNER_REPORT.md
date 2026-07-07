# TAE Paper Experiment Runner Report

**Generated:** 2026-07-07T13:46:14+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE
**Live promotion allowed:** false

> **PAPER_ONLY experiment scoring — read-only simulation from existing SSOT; no broker execution**

## Executive summary

- Queue size: **21**
- Experiments run: **21**
- PROMISING: **10**
- CONTINUE_TESTING: **5**
- REJECT: **0**
- NEEDS_MORE_DATA: **6**

## Top experiments

| rank | hypothesis_id | type | verdict | profit Δ USD | risk Δ | cap eff Δ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `LTB-DPE-PHIL-001` | DPE_PHILOSOPHY | PROMISING | 50.07 | -0.05 | 0.22 |
| 2 | `LTB-OPP-HSBA.L-01` | OPPORTUNITY_COST | PROMISING | 37.38 | -0.06 | 3.6 |
| 3 | `LTB-OPP-MU-02` | OPPORTUNITY_COST | PROMISING | 35.9 | -0.06 | 2.9 |
| 4 | `LTB-OPP-AMAT-03` | OPPORTUNITY_COST | PROMISING | 35.25 | -0.06 | 2.9 |
| 5 | `LTB-PROT-AMAT` | PROFIT_PROTECTION | PROMISING | 26.65 | -0.18 | -0.09 |
| 6 | `LTB-PROT-MU` | PROFIT_PROTECTION | PROMISING | 16.0 | -0.18 | -0.09 |
| 7 | `LTB-PROT-MRK` | PROFIT_PROTECTION | PROMISING | 10.33 | -0.0369 | -0.96 |
| 8 | `LTB-PROT-SIE.DE` | PROFIT_PROTECTION | PROMISING | 8.91 | -0.063 | -0.51 |
| 9 | `LTB-PROT-LLY` | PROFIT_PROTECTION | PROMISING | 8.63 | -0.063 | -0.65 |
| 10 | `LTB-PROT-AAPL` | PROFIT_PROTECTION | PROMISING | 5.59 | -0.063 | -0.51 |
| 11 | `LTB-LIFE-LLY-05` | WINNER_LIFECYCLE | CONTINUE_TESTING | 4.96 | -0.042 | 2.58 |
| 12 | `LTB-LIFE-SPY-04` | WINNER_LIFECYCLE | CONTINUE_TESTING | 4.37 | 0.0171 | -1.84 |
| 13 | `LTB-LIFE-PM-03` | WINNER_LIFECYCLE | CONTINUE_TESTING | 4.27 | 0.015 | -1.97 |
| 14 | `LTB-PROT-PG` | PROFIT_PROTECTION | CONTINUE_TESTING | 4.2 | -0.0396 | -0.98 |
| 15 | `LTB-PROT-HSBA.L` | PROFIT_PROTECTION | CONTINUE_TESTING | 2.2 | -0.18 | -0.0 |

## Closed validation loop

- Input: `runtime_outputs/learning_to_profit/paper_experiment_queue.jsonl`
- Input: `runtime_outputs/learning_to_profit/hypotheses.json`
- Output: `runtime_outputs/learning_to_profit/experiment_results.json`
- Each hypothesis receives measurable baseline vs hypothesis deltas and a verdict.

## Paper decision validation

- Consumes: `runtime_outputs/paper_decisions/paper_decisions.jsonl` (deduplicated with `paper_decisions.json`)
- Output: `runtime_outputs/paper_decisions/decision_validation_results.json`
- Detail report: `TAE_PAPER_DECISION_VALIDATION_REPORT.md`

- Unique decisions validated: **25** (raw rows read: 50)
- PROMISING: **2** | CONTINUE: **5** | NEEDS_MORE_DATA: **18** | REJECT: **0**

### Top ranked validated decisions

| rank | ticker | action | verdict | profit Δ | reason |
| --- | --- | --- | --- | --- | --- |
| 1 | AMAT | PROTECT_PAPER | PROMISING | 41.09 | PROMISING: PROTECT_PAPER on AMAT simulates +$41.09 profit with riskΔ=- |
| 2 | HSBA.L | SELL_PAPER | PROMISING | 37.38 | PROMISING: SELL_PAPER on HSBA.L simulates +$37.38 profit with riskΔ=-0 |
| 3 | LLY | PROTECT_PAPER | CONTINUE_TESTING | 8.63 | CONTINUE: PROTECT_PAPER on LLY shows modest simulated gain +$8.63 (ris |
| 4 | SPY | HOLD_PAPER | CONTINUE_TESTING | 4.37 | CONTINUE: HOLD_PAPER on SPY shows modest simulated gain +$4.37 (riskΔ= |
| 5 | PM | HOLD_PAPER | CONTINUE_TESTING | 4.27 | CONTINUE: HOLD_PAPER on PM shows modest simulated gain +$4.27 (riskΔ=0 |
| 6 | PG | HOLD_PAPER | CONTINUE_TESTING | 4.2 | CONTINUE: HOLD_PAPER on PG shows modest simulated gain +$4.20 (riskΔ=0 |
| 7 | AZN.L | SELL_PAPER | CONTINUE_TESTING | 0.0 | CONTINUE: SELL_PAPER on AZN.L shows modest simulated gain +$0.00 (risk |
| 8 | MU | PROTECT_PAPER | NEEDS_MORE_DATA | 35.9 | NEEDS_MORE_DATA: PROTECT_PAPER on MU — missing: confidence 0.38 below  |
| 9 | MRK | BUY_PAPER | NEEDS_MORE_DATA | 12.83 | NEEDS_MORE_DATA: BUY_PAPER on MRK — missing: confidence 0.25 below 0.4 |
| 10 | SIE.DE | HOLD_PAPER | NEEDS_MORE_DATA | 8.91 | NEEDS_MORE_DATA: HOLD_PAPER on SIE.DE — missing: confidence 0.30 below |

## Safety confirmation

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| READ_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_LIVE_CHANGE | ✅ |
| live_promotion_allowed | **false** |
| portfolio.csv modified | **false** |
| live_bot.py modified | **false** |
