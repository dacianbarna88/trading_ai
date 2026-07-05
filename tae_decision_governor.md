# TAE Decision Governor (X.DECISION-1)

**Generated:** 2026-07-05T20:44:08
**Mode:** SHADOW_ONLY | **Live impact:** NONE

> READ-ONLY advisory VIEW. No orders. No portfolio changes.

## Executive summary

- **Overall advisory posture:** NOT_READY
- **Shadow readiness:** NOT_READY
- **Live advisory action:** SELL_ADVISORY
- **block_new_buy:** False

## Sources loaded

- ✅ tae_committee_runtime.json
- ✅ tae_confidence_evolution.json
- ✅ tae_decision_replay.json
- ✅ tae_knowledge_base.json
- ✅ tae_live_advisory.json
- ✅ tae_profit_protection_shadow.json
- ✅ tae_profit_protection_validation.json
- ✅ tae_stop_reentry_cooldown_audit.json
- ✅ tae_unified_runtime.json
- ✅ weighted_committee_decision.txt

## Posture counts

- **ALLOWED:** 44
- **BLOCKED:** 0
- **INSUFFICIENT_DATA:** 0
- **WATCH:** 19

## Blocker summary

- **SHADOW_GATES_NOT_READY** — PROTECT=WATCH COOLDOWN=NOT_READY [tae_decision_replay.json]
- **PROTECT_GATES_FAILED** — G3 [tae_profit_protection_validation.json]
- **COOLDOWN_GATES_FAILED** — G4, G5 [tae_stop_reentry_cooldown_audit.json]
- **DO_NOT_PROMOTE** — Shadow advisory — gates not passed [tae_decision_replay.json]
- **DO_NOT_PROMOTE** — DO_NOT_PROMOTE_TO_ADVISORY_YET [tae_decision_replay.json]
- **DO_NOT_PROMOTE** — DO_NOT_PROMOTE_TO_LIVE [tae_decision_replay.json]
- **CONFIDENCE_EVOLUTION_NOT_READY** — Confidence evolution promotion readiness NOT_READY [tae_confidence_evolution.json]

## Advisory notes

- Intraday gains evaporate (exit/protection gap) while rapid STOP→reentry churn compounds losses on high-score names.
- Primary shadow cause: MISSED_PROFIT_PROTECTION
- Best shadow hypothesis: shadow_trailing_1
- Live advisory action: SELL_ADVISORY
- Committee: BUY

## Per-ticker posture (sample)

| Ticker | Posture | Signal | Score | Notes |
|--------|---------|--------|-------|-------|
| AAPL | **WATCH** | WAIT | 40.0 | STOP reentry churn: STOP→BUY after 21589.08m; outcome=REENTRY_SECOND_STOP |
| ABBV | **WATCH** | TAKE PROFIT | 40.0 | TAKE PROFIT signal — exit advisory context only |
| ADBE | **ALLOWED** | WAIT | 0.0 | - |
| AIR.PA | **WATCH** | TAKE PROFIT | 40.0 | TAKE PROFIT signal — exit advisory context only |
| ALV.DE | **WATCH** | TAKE PROFIT | 40.0 | TAKE PROFIT signal — exit advisory context only |
| AMAT | **WATCH** | TAKE PROFIT | 40.0 | Shadow score decay candidate (SCORE_DECAY_SHADOW) |
| AMD | **ALLOWED** | WAIT | 90.0 | - |
| AMZN | **ALLOWED** | WAIT | 20.0 | - |
| AVGO | **ALLOWED** | WAIT | 20.0 | - |
| AZN.L | **WATCH** | STRONG BUY | 80.0 | Shadow promotion gates NOT_READY — observation only |
| BAC | **ALLOWED** | WAIT | 65.0 | - |
| BP.L | **ALLOWED** | WAIT | 0.0 | - |
| BRK-B | **ALLOWED** | WAIT | 65.0 | - |
| CAT | **ALLOWED** | WAIT | 90.0 | - |
| COIN | **ALLOWED** | WAIT | 0.0 | - |
| COST | **ALLOWED** | WAIT | 0.0 | - |
| CRM | **ALLOWED** | WAIT | 0.0 | - |
| CRWD | **ALLOWED** | WAIT | 45.0 | - |
| CSCO | **ALLOWED** | WAIT | 45.0 | - |
| DIA | **WATCH** | STRONG BUY | 80.0 | Shadow promotion gates NOT_READY — observation only |

_… and 43 more tickers._

## Recommendations (SHADOW_ONLY)

- DO_NOT_PROMOTE_TO_ADVISORY_YET
- TEST_TRAILING_SHADOW
- CONTINUE_OBSERVATION
- DO_NOT_PROMOTE_TO_LIVE
- TEST_15M_COOLDOWN_SHADOW
- SCORE_DECAY_SHADOW
- INSUFFICIENT_DATA
- PRIORITIZE_TRACKING

*Governor VIEW only. Upstream SSOT files remain authoritative.*
