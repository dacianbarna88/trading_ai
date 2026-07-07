# TAE Learning-to-Profit Bridge Report

**Generated:** 2026-07-07T11:24:54+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_EXECUTION
**Live promotion allowed:** false

> **PAPER_ONLY: ranked hypotheses and experiment queue — no trade execution, no live promotion**

## Executive summary

- Hypotheses generated: **21**
- Sources loaded: **13**
- Paper queue entries: **21**

## Hypothesis types

- **DPE_PHILOSOPHY**: 1
- **OPPORTUNITY_COST**: 3
- **PROFIT_PROTECTION**: 12
- **WINNER_LIFECYCLE**: 5

## Top ranked PAPER hypotheses

### 1. `LTB-LIFE-PG-01` — WINNER_LIFECYCLE

- **Tickers:** PG
- **Confidence:** 0.58 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_HOLD`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json

### 2. `LTB-LIFE-MRK-02` — WINNER_LIFECYCLE

- **Tickers:** MRK
- **Confidence:** 0.57 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_HOLD`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json

### 3. `LTB-LIFE-PM-03` — WINNER_LIFECYCLE

- **Tickers:** PM
- **Confidence:** 0.6 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_HOLD`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json

### 4. `LTB-DPE-PHIL-001` — DPE_PHILOSOPHY

- **Tickers:** (portfolio-level)
- **Confidence:** 0.755 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER dual-arm weighting experiment shifts toward COLLABORATIVE philosophy (26.2% competitive / 73.8% collaborative).
- **PAPER action:** `PAPER_DPE_PHILOSOPHY_WEIGHT`
- **Validation:** PAPER weighted arm beats control on profit_capture_rate and capital_efficiency over 30-day window with confidence >=55%.
- **Rejection:** Reject if weighted philosophy underperforms both pure arms on total_pnl and max_drawdown.
- **Sources:** runtime_outputs/dpe/adaptive/adaptive.json, runtime_outputs/dpe/result_evaluator/evaluation.json, runtime_outputs/dpe/learning/learning.json

### 5. `LTB-LIFE-SPY-04` — WINNER_LIFECYCLE

- **Tickers:** SPY
- **Confidence:** 0.64 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_HOLD`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json

### 6. `LTB-LIFE-LLY-05` — WINNER_LIFECYCLE

- **Tickers:** LLY
- **Confidence:** 0.82 | **Risk:** MEDIUM
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_TRIM`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json

### 7. `LTB-OPP-HSBA.L-01` — OPPORTUNITY_COST

- **Tickers:** HSBA.L
- **Confidence:** 0.88 | **Risk:** MEDIUM
- **Target metric:** opportunity_cost_total
- **Mechanism:** PAPER reallocation unlocks capital locked in low-upside positions to capture missed profit opportunities.
- **PAPER action:** `PAPER_REALLOCATION`
- **Validation:** PAPER reallocation reduces opportunity_cost_total by >=10% vs locked-capital control arm.
- **Rejection:** Reject if reallocation increases churn or realized losses without offsetting opportunity gain.
- **Sources:** tae_opportunity_cost_ledger.json

### 8. `LTB-OPP-MU-02` — OPPORTUNITY_COST

- **Tickers:** MU
- **Confidence:** 0.88 | **Risk:** MEDIUM
- **Target metric:** opportunity_cost_total
- **Mechanism:** PAPER reallocation unlocks capital locked in low-upside positions to capture missed profit opportunities.
- **PAPER action:** `PAPER_REALLOCATION`
- **Validation:** PAPER reallocation reduces opportunity_cost_total by >=10% vs locked-capital control arm.
- **Rejection:** Reject if reallocation increases churn or realized losses without offsetting opportunity gain.
- **Sources:** tae_opportunity_cost_ledger.json

### 9. `LTB-PROT-AMAT` — PROFIT_PROTECTION

- **Tickers:** AMAT
- **Confidence:** 0.9 | **Risk:** MEDIUM
- **Target metric:** profit_at_risk_reduction
- **Mechanism:** PAPER trailing/protect/trim policy reduces giveback from peak profit.
- **PAPER action:** `PAPER_TRAILING_PROTECT_TRIM`
- **Validation:** PAPER protect/trim arm reduces missed_opportunity_usd by >=15% vs hold baseline on matched ticker cohort.
- **Rejection:** Reject if protection trims winners before peak capture and profit_capture_rate falls vs control.
- **Sources:** tae_profit_protection_shadow.json

### 10. `LTB-OPP-AMAT-03` — OPPORTUNITY_COST

- **Tickers:** AMAT
- **Confidence:** 0.88 | **Risk:** MEDIUM
- **Target metric:** opportunity_cost_total
- **Mechanism:** PAPER reallocation unlocks capital locked in low-upside positions to capture missed profit opportunities.
- **PAPER action:** `PAPER_REALLOCATION`
- **Validation:** PAPER reallocation reduces opportunity_cost_total by >=10% vs locked-capital control arm.
- **Rejection:** Reject if reallocation increases churn or realized losses without offsetting opportunity gain.
- **Sources:** tae_opportunity_cost_ledger.json

## Outputs

- `runtime_outputs/learning_to_profit/hypotheses.json`
- `runtime_outputs/learning_to_profit/paper_experiment_queue.jsonl`

## Safety confirmation

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_LIVE_EXECUTION | ✅ |
| live_promotion_allowed | **false** |
| portfolio.csv modified | **false** |
| live_bot.py modified | **false** |

## Required type coverage

- CAPITAL_EFFICIENCY: ⚠️ missing
- PROFIT_PROTECTION: ✅
- OPPORTUNITY_COST: ✅
- WINNER_LIFECYCLE: ✅
- DPE_PHILOSOPHY: ✅
- STALE_LEARNING: ⚠️ missing
