# TAE Adaptive Weights Report

**Generated:** 2026-07-07T15:26:25+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION

- Actions weighted: **7**
- Max daily delta cap: **0.02**
- Weight range: **0.85–1.15**

## Action weights

| action | previous | new | delta | cap | reason |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 0.985 | 0.982 | -0.003 | False | BUY risk adjustment -0.0030; confidence evolution caution: {'STRONGER': ['SCORE_ |
| SELL_PAPER | 1.0835 | 1.1002 | 0.0167 | False | PROMISING×1 → +0.0040; CONTINUE_TESTING×2 → +0.0027; longitudinal hint bias +0.5 |
| HOLD_PAPER | 1.005 | 1.006 | 0.001 | False | CONTINUE_TESTING×3 → +0.0020; NEEDS_MORE_DATA×3 → -0.0010 |
| REDUCE_PAPER | 1.0 | 1.0 | 0.0 | False | no evidence change — weight preserved |
| PROTECT_PAPER | 0.9993 | 0.9987 | -0.0006 | False | PROMISING×1 → +0.0040; NEEDS_MORE_DATA×2 → -0.0013; longitudinal hint bias -0.16 |
| ROTATE_PAPER | 1.0 | 1.0 | 0.0 | False | no evidence change — weight preserved |
| SKIP_PAPER | 0.94 | 0.928 | -0.012 | False | NEEDS_MORE_DATA×13 → -0.0020; longitudinal hint bias -0.500 |

## Evidence sources

- Validation: `runtime_outputs/paper_decisions/decision_validation_results.json`
- Longitudinal hints: `runtime_outputs/longitudinal_memory/adaptation_hints.json`
- Confidence evolution: `tae_confidence_evolution.json`
- DPE adaptive: `runtime_outputs/dpe/adaptive/adaptive.json`

## PDE consumption

- Weights file: `runtime_outputs/adaptive_weights/paper_action_weights.json`
- Applied in `score_actions_for_ticker()` as score multipliers
- Decisions include `adaptive_weight_evidence` field
