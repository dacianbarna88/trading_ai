# TAE Paper Experiment Runner Report

**Generated:** 2026-09-03T13:15:17+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE
**Live promotion allowed:** false

> **PAPER_ONLY experiment scoring — read-only simulation from existing SSOT; no broker execution**

## Executive summary

- Queue size: **17**
- Experiments run: **17**
- PROMISING: **8**
- CONTINUE_TESTING: **3**
- REJECT: **0**
- NEEDS_MORE_DATA: **6**

## Top experiments

| rank | hypothesis_id | type | verdict | profit Δ USD | risk Δ | cap eff Δ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `LTB-DPE-PHIL-001` | DPE_PHILOSOPHY | PROMISING | 787.65 | 0.03 | 3.6 |
| 2 | `LTB-OPP-HSBA.L-01` | OPPORTUNITY_COST | PROMISING | 37.38 | -0.0552 | 3.6 |
| 3 | `LTB-OPP-MU-02` | OPPORTUNITY_COST | PROMISING | 35.9 | -0.06 | 2.9 |
| 4 | `LTB-OPP-AMAT-03` | OPPORTUNITY_COST | PROMISING | 35.25 | -0.06 | 2.9 |
| 5 | `LTB-PROT-PPG-HSBA.L` | PROFIT_PROTECTION | PROMISING | 28.32 | -0.1656 | -0.0 |
| 6 | `LTB-PROT-PPG-MU` | PROFIT_PROTECTION | PROMISING | 27.19 | -0.18 | -0.09 |
| 7 | `LTB-PROT-PPG-AMAT` | PROFIT_PROTECTION | PROMISING | 26.7 | -0.18 | -0.09 |
| 8 | `LTB-LOSS-LOSS-CRYSTALLIZATION-ABF990` | LOSS_PATTERN_STOP_V1 | PROMISING | 15.69 | -0.0229 | -0.61 |
| 9 | `LTB-LIFE-SPY-03` | WINNER_LIFECYCLE | CONTINUE_TESTING | 4.09 | 0.0118 | -1.87 |
| 10 | `LTB-LIFE-PM-05` | WINNER_LIFECYCLE | CONTINUE_TESTING | 3.9 | 0.0118 | -1.94 |
| 11 | `LTB-LIFE-LLY-04` | WINNER_LIFECYCLE | CONTINUE_TESTING | 3.32 | -0.0329 | 2.72 |
| 12 | `LTB-PROT-PPG-QQQ` | PROFIT_PROTECTION | NEEDS_MORE_DATA | 0.94 | -0.1471 | -0.44 |
| 13 | `LTB-LIFE-PG-02` | WINNER_LIFECYCLE | NEEDS_MORE_DATA | 0.8 | 0.0103 | -1.96 |
| 14 | `LTB-LIFE-MRK-01` | WINNER_LIFECYCLE | NEEDS_MORE_DATA | 0.31 | 0.0102 | -1.91 |
| 15 | `LTB-STALE-001` | STALE_LEARNING | NEEDS_MORE_DATA | 0.0 | 0.0 | 0.0 |

## Closed validation loop

- Input: `runtime_outputs/learning_to_profit/paper_experiment_queue.jsonl`
- Input: `runtime_outputs/learning_to_profit/hypotheses.json`
- Output: `runtime_outputs/learning_to_profit/experiment_results.json`
- Each hypothesis receives measurable baseline vs hypothesis deltas and a verdict.

## Paper decision validation

- Also consumes: `runtime_outputs/paper_decisions/paper_decisions.jsonl` (deduplicated with `paper_decisions.json`)
- Output: `runtime_outputs/paper_decisions/decision_validation_results.json`
- Detail report: `TAE_PAPER_DECISION_VALIDATION_REPORT.md`
- Each validated decision includes ranked verdict, profit/risk/cap-eff deltas, reason, and evidence summary.

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
