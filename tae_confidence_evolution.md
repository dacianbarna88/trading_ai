# TAE Confidence Evolution (X.KNOWLEDGE-1B)

**Generated:** 2026-07-02T17:49:47
**Mode:** SHADOW_ONLY | **Live impact:** NONE

> SHADOW_ONLY — Score decay and confidence updates are advisory VIEW only. Live scores are NOT modified.

## Executive summary

- **Replay primary cause:** MISSED_PROFIT_PROTECTION
- **Replay secondary cause:** STOP_REENTRY_CHURN
- **Score persistence cases:** 8
- **Second STOP cases:** 2
- **Score decay candidates:** 2
- **Promotion readiness:** NOT_READY

## Evidence sources

- ✅ tae_stop_reentry_cooldown_audit.json
- ✅ tae_decision_replay.json
- ✅ tae_profit_protection_validation.json
- ✅ tae_knowledge_base.json
- ✅ portfolio.csv

## Dataset health

- stop_reentry_cases: **8**
- score_persistence_cases: **8**
- second_stop_cases: **2**
- protect_observations: **26**
- data_quality: **LIMITED**
- sample_warning: **True**

## Confidence changes

- **SCORE_PERSISTENCE_AFTER_STOP** — HIGH → **HIGH** (Δ+0) | trend=IMPROVING | status=LEARNING
  - 8/8 reentries retained score≥80 + STRONG BUY after STOP
- **STOP_REENTRY_CHURN** — LOW → **MEDIUM** (Δ+1) | trend=IMPROVING | status=WATCH
  - 5 immediate reentries (≤5m); 2 second STOPs; confirmed damage ≈75.71 USD (MU)
- **MISSED_PROFIT_PROTECTION** — LOW → **MEDIUM** (Δ+1) | trend=IMPROVING | status=LEARNING
  - X.REPLAY-1 primary=MISSED_PROFIT_PROTECTION; shadow protection Δ vs HOLD +616.18 USD (26 obs)
- **TRAILING_1_PROTECTION_HYPOTHESIS** — LOW → **MEDIUM** (Δ+1) | trend=IMPROVING | status=WATCH
  - Best strategy shadow_trailing_1 total 579.05 USD; win_rate=0.5385
- **COOLDOWN_15M_HYPOTHESIS** — LOW → **MEDIUM** (Δ+1) | trend=STABLE | status=DO_NOT_PROMOTE
  - cooldown_15m net effect 23.98 USD; sample 8 reentries

## Score decay candidates

1. **MU** — score 100.0 → shadow 80.0 for 30m | REENTRY_SECOND_STOP | score 100 persisted after STOP; reentry in 1.33m; second STOP confirmed; negative leg PnL -75.71 USD
2. **MU** — score 100.0 → shadow 80.0 for 30m | REENTRY_OPEN_UNREALIZED | score 100 persisted after STOP; reentry in 1.32m; negative leg PnL -24.75 USD

## What got stronger

- SCORE_PERSISTENCE_AFTER_STOP
- STOP_REENTRY_CHURN
- MISSED_PROFIT_PROTECTION
- TRAILING_1_PROTECTION_HYPOTHESIS

## What got weaker

- (none)

## What remains insufficient

- (none)

## Promotion readiness

- PROTECT-2: NOT_READY
- COOLDOWN-1: NOT_READY
- **Final:** NOT_READY

## Final recommendation

- Next module: **X.KNOWLEDGE-1C — wire SCORE_DECAY_SHADOW into knowledge materialization**
- Do NOT promote: DO_NOT_PROMOTE_TO_LIVE, DO_NOT_PROMOTE_TO_ADVISORY_YET

## Recommendations (SHADOW_ONLY)

- SCORE_DECAY_SHADOW
- TEST_15M_COOLDOWN_SHADOW
- TEST_TRAILING_SHADOW
- CONTINUE_OBSERVATION
- DO_NOT_PROMOTE_TO_ADVISORY_YET
- INSUFFICIENT_DATA

*Extension VIEW only. Upstream SSOT files remain authoritative.*
