# TAE Adaptive Weights Report

**Generated:** 2026-09-03T13:02:33+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION

- Actions weighted: **7**
- Max daily delta cap: **0.02**
- Weight range: **0.85–1.15**

## Action weights

| action | previous | new | delta | cap | reason |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 1.15 | 1.15 | 0.0 | True | PROMISING×30 → +0.0028 [discounted: real evidence present]; NEEDS_MORE_DATA×8 →  |
| SELL_PAPER | 0.9322 | 0.9395 | 0.0073 | False | longitudinal hint bias +0.167; longitudinal knowledge rules KNOW-SELL_PAPER; act |
| HOLD_PAPER | 1.15 | 1.15 | 0.0 | True | PROMISING×4 → +0.0013 [discounted: real evidence present]; CONTINUE_TESTING×7 →  |
| REDUCE_PAPER | 1.15 | 1.15 | 0.0 | False | experiment CONTINUE_TESTING×1 [LTB-LIFE-LLY-04] → +0.0030 |
| PROTECT_PAPER | 1.15 | 1.15 | 0.0 | True | NEEDS_MORE_DATA×1 → -0.0006 [discounted: real evidence present]; experiment PROM |
| ROTATE_PAPER | 1.15 | 1.15 | 0.0 | False | experiment PROMISING×3 [LTB-OPP-HSBA.L-01,LTB-OPP-MU-02,LTB-OPP-AMAT-03] → +0.00 |
| SKIP_PAPER | 0.85 | 0.85 | 0.0 | False | NEEDS_MORE_DATA×48 → -0.0020; longitudinal hint bias -0.500; longitudinal knowle |

## Evidence sources

- Validation: `runtime_outputs/paper_decisions/decision_validation_results.json`
- Experiment results (actionable only): `runtime_outputs/learning_to_profit/experiment_results.json`
- Longitudinal hints: `runtime_outputs/longitudinal_memory/adaptation_hints.json`
- Longitudinal knowledge: `runtime_outputs/longitudinal_memory/knowledge.json`
- Paper execution attribution: `runtime_outputs/paper_execution/rule_outcome_attribution.json`
- Confidence evolution: `tae_confidence_evolution.json`
- DPE adaptive: `runtime_outputs/dpe/adaptive/adaptive.json`

## PDE consumption

- Weights file: `runtime_outputs/adaptive_weights/paper_action_weights.json`
- Applied in `score_actions_for_ticker()` as score multipliers
- Decisions include `adaptive_weight_evidence` field
