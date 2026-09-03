# TAE Learning-to-Profit Bridge Report

**Generated:** 2026-09-03T13:15:17+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_EXECUTION
**Live promotion allowed:** false

> **PAPER_ONLY: ranked hypotheses and experiment queue — no trade execution, no live promotion**

## Executive summary

- Hypotheses generated: **17**
- Sources loaded: **14**
- Paper queue entries: **17**

## Hypothesis types

- **DPE_PHILOSOPHY**: 1
- **LOSS_PATTERN_STOP_V1**: 1
- **OPPORTUNITY_COST**: 3
- **PROFIT_PROTECTION**: 5
- **STALE_LEARNING**: 2
- **WINNER_LIFECYCLE**: 5

## Top ranked PAPER hypotheses

### 1. `LTB-DPE-PHIL-001` — DPE_PHILOSOPHY

- **Tickers:** (portfolio-level)
- **Confidence:** 0.721 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER dual-arm weighting experiment shifts toward COMPETITIVE philosophy (63.8% competitive / 36.2% collaborative).
- **PAPER action:** `PAPER_DPE_PHILOSOPHY_WEIGHT`
- **Validation:** PAPER weighted arm beats control on profit_capture_rate and capital_efficiency over 30-day window with confidence >=55%.
- **Rejection:** Reject if weighted philosophy underperforms both pure arms on total_pnl and max_drawdown.
- **Sources:** runtime_outputs/dpe/adaptive/adaptive.json, runtime_outputs/dpe/result_evaluator/evaluation.json, runtime_outputs/dpe/learning/learning.json, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 2. `LTB-STALE-001` — STALE_LEARNING

- **Tickers:** (portfolio-level)
- **Confidence:** 0.7 | **Risk:** HIGH
- **Target metric:** decision_freshness
- **Mechanism:** Maintenance experiment refreshes stale advisory/learning artifacts so downstream PAPER experiments use current evidence.
- **PAPER action:** `PAPER_MAINTENANCE_REFRESH`
- **Validation:** All critical SSOT artifacts regenerated within freshness SLA; learning-profit bridge produces >=3 non-stale hypotheses.
- **Rejection:** Reject maintenance cycle if regenerated artifacts fail schema validation or morning-audit freshness score decreases.
- **Sources:** infrastructure_freshness_audit, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 3. `LTB-LIFE-MRK-01` — WINNER_LIFECYCLE

- **Tickers:** MRK
- **Confidence:** 0.64 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_HOLD`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 4. `LTB-LIFE-PG-02` — WINNER_LIFECYCLE

- **Tickers:** PG
- **Confidence:** 0.64 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_HOLD`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 5. `LTB-LIFE-SPY-03` — WINNER_LIFECYCLE

- **Tickers:** SPY
- **Confidence:** 0.58 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_HOLD`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 6. `LTB-LOSS-LOSS-CRYSTALLIZATION-ABF990` — LOSS_PATTERN_STOP_V1

- **Tickers:** ABBV, ADSK, AIR.PA, AMD, ANET, BLK, BP.L, CDNS, CRWD, DELL, FTNT, GE, GS, HD, LLY, MRK, PG, PM, SAP.DE, SIE.DE
- **Confidence:** 0.83 | **Risk:** HIGH
- **Target metric:** realized_exit_pnl
- **Mechanism:** A one-dimensional PAPER exit-policy challenger tests whether timing changes reduce repeated realized losses without weakening hard-risk controls.
- **PAPER action:** `PAPER_EXIT_POLICY_CHALLENGER`
- **Validation:** PAPER challenger improves matched-cohort realized exit PnL with no increase in maximum accepted loss.
- **Rejection:** Reject if delayed/trailing exit increases drawdown, hard-risk breaches, or matched-cohort realized loss.
- **Sources:** learning_attribution, rule_outcome_attribution, parallel_v1_journals, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 7. `LTB-LIFE-LLY-04` — WINNER_LIFECYCLE

- **Tickers:** LLY
- **Confidence:** 0.6 | **Risk:** MEDIUM
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_TRIM`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 8. `LTB-LIFE-PM-05` — WINNER_LIFECYCLE

- **Tickers:** PM
- **Confidence:** 0.72 | **Risk:** LOW
- **Target metric:** profit_capture_rate
- **Mechanism:** PAPER lifecycle policy holds winners longer or trims later to improve capture vs premature exit.
- **PAPER action:** `PAPER_LIFECYCLE_HOLD`
- **Validation:** PAPER lifecycle arm improves profit_capture_rate on ticker cohort without increasing collapse_probability.
- **Rejection:** Reject if lifecycle experiment increases drawdown or missed_usd vs hold baseline over 30 days.
- **Sources:** tae_winner_lifecycle_profiler.json, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 9. `LTB-OPP-HSBA.L-01` — OPPORTUNITY_COST

- **Tickers:** HSBA.L
- **Confidence:** 0.88 | **Risk:** MEDIUM
- **Target metric:** opportunity_cost_total
- **Mechanism:** PAPER reallocation unlocks capital locked in low-upside positions to capture missed profit opportunities.
- **PAPER action:** `PAPER_REALLOCATION`
- **Validation:** PAPER reallocation reduces opportunity_cost_total by >=10% vs locked-capital control arm.
- **Rejection:** Reject if reallocation increases churn or realized losses without offsetting opportunity gain.
- **Sources:** tae_opportunity_cost_ledger.json, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

### 10. `LTB-OPP-MU-02` — OPPORTUNITY_COST

- **Tickers:** MU
- **Confidence:** 0.88 | **Risk:** MEDIUM
- **Target metric:** opportunity_cost_total
- **Mechanism:** PAPER reallocation unlocks capital locked in low-upside positions to capture missed profit opportunities.
- **PAPER action:** `PAPER_REALLOCATION`
- **Validation:** PAPER reallocation reduces opportunity_cost_total by >=10% vs locked-capital control arm.
- **Rejection:** Reject if reallocation increases churn or realized losses without offsetting opportunity gain.
- **Sources:** tae_opportunity_cost_ledger.json, historical_intelligence.csv, strategic_intelligence_summary.txt, horizon_vote_summary.txt

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
- STALE_LEARNING: ✅
