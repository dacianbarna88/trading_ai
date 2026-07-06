# TAE Profit Decision Governor v1

**Generated:** 2026-07-06T18:48:10
**Mode:** SHADOW_ONLY — NONE
**Final verdict:** PDG_SHADOW_READY_FOR_OBSERVATION

> **NO BUY / NO SELL — SHADOW_ONLY profit decision VIEW**

Profit protect pipeline VIEW — reconciles PDC + PCE; live execution remains live_bot.py

## Executive summary

- **Overall profit posture:** WATCH
- **Validation readiness:** WATCH
- **Committee verdict:** PDC_SHADOW_READY_FOR_OBSERVATION
- **Context verdict:** PCE_SHADOW_READY_FOR_OBSERVATION
- **Total tickers:** 12
- **Average governor score:** 57.3

## Sources loaded

- ✅ tae_profit_committee_learning.json
- ✅ tae_profit_context_engine.json
- ✅ tae_profit_context_learning.json
- ✅ tae_profit_decision_committee.json
- ✅ tae_profit_intelligence_brain.json
- ✅ tae_profit_memory_engine.json
- ✅ tae_profit_protection_shadow.json
- ✅ tae_profit_protection_validation.json

## Posture counts

- **INSUFFICIENT_DATA:** 0
- **KEEP_WINNER_SHADOW:** 4
- **OBSERVE_SHADOW:** 1
- **PROTECT_SHADOW:** 2
- **TRAIL_SHADOW:** 2
- **WATCH_SHADOW:** 3

## Alignment counts

- **ALIGNED:** 8
- **CONTEXT_ESCALATES:** 4

## Blocker summary

- **VALIDATION_GATES_FAILED** — G3 [tae_profit_protection_validation.json]
- **VALIDATION_NOT_READY** — PROMISING_BUT_NOT_READY [tae_profit_protection_validation.json]
- **SHADOW_ONLY** — No live or advisory integration — observation VIEW only [tae_profit_decision_governor.py]

## Top 5 PROTECT_SHADOW

| ticker | governor score | final rec | alignment |
| --- | --- | --- | --- |
| AMAT | 24.9 | PARTIAL_PROTECT_SHADOW | ALIGNED |
| MU | 24.9 | PARTIAL_PROTECT_SHADOW | ALIGNED |

## Top 5 KEEP_WINNER_SHADOW

| ticker | governor score | final rec | PCE verdict |
| --- | --- | --- | --- |
| MRK | 94.9 | HOLD | KEEP_WINNER |
| PM | 91.2 | HOLD | KEEP_WINNER |
| SPY | 89.5 | HOLD | KEEP_WINNER |
| PG | 82.7 | HOLD | KEEP_WINNER |

## Per-ticker governor view

| ticker | governor score | posture | final rec | PDC weighted | PCE verdict | alignment | conf |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MRK | 94.9 | KEEP_WINNER_SHADOW | HOLD | HOLD | KEEP_WINNER | ALIGNED | HIGH |
| PM | 91.2 | KEEP_WINNER_SHADOW | HOLD | HOLD | KEEP_WINNER | ALIGNED | HIGH |
| SPY | 89.5 | KEEP_WINNER_SHADOW | HOLD | HOLD | KEEP_WINNER | ALIGNED | HIGH |
| PG | 82.7 | KEEP_WINNER_SHADOW | HOLD | HOLD | KEEP_WINNER | ALIGNED | HIGH |
| MC.PA | 55.6 | OBSERVE_SHADOW | OBSERVE | OBSERVE | NORMAL_PULLBACK | ALIGNED | HIGH |
| SIE.DE | 61.6 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | HIGH |
| AAPL | 59.2 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | HIGH |
| QQQ | 46.9 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | HIGH |
| LLY | 31.8 | TRAIL_SHADOW | TRAIL_PROTECT_SHADOW | TRAIL_PROTECT_SHADOW | NORMAL_PULLBACK | ALIGNED | HIGH |
| HSBA.L | 24.9 | TRAIL_SHADOW | TRAIL_PROTECT_SHADOW | WATCH | PROTECT_NOW | CONTEXT_ESCALATES | HIGH |
| AMAT | 24.9 | PROTECT_SHADOW | PARTIAL_PROTECT_SHADOW | PARTIAL_PROTECT_SHADOW | CONTEXT_WEAKENING | ALIGNED | HIGH |
| MU | 24.9 | PROTECT_SHADOW | PARTIAL_PROTECT_SHADOW | PARTIAL_PROTECT_SHADOW | CONTEXT_WEAKENING | ALIGNED | HIGH |

## Per-ticker explanations

### MRK — KEEP_WINNER_SHADOW
SHADOW_ONLY governor for MRK: PDC=HOLD (v1=HOLD), PCE=KEEP_WINNER (score=89.8), combined_rank=0.00 → HOLD (KEEP_WINNER_SHADOW). Alignment=ALIGNED, governor_score=94.9.

### PM — KEEP_WINNER_SHADOW
SHADOW_ONLY governor for PM: PDC=HOLD (v1=HOLD), PCE=KEEP_WINNER (score=82.4), combined_rank=0.00 → HOLD (KEEP_WINNER_SHADOW). Alignment=ALIGNED, governor_score=91.2.

### SPY — KEEP_WINNER_SHADOW
SHADOW_ONLY governor for SPY: PDC=HOLD (v1=HOLD), PCE=KEEP_WINNER (score=79.1), combined_rank=0.00 → HOLD (KEEP_WINNER_SHADOW). Alignment=ALIGNED, governor_score=89.5.

### PG — KEEP_WINNER_SHADOW
SHADOW_ONLY governor for PG: PDC=HOLD (v1=NO_ACTION), PCE=KEEP_WINNER (score=82.4), combined_rank=0.00 → HOLD (KEEP_WINNER_SHADOW). Alignment=ALIGNED, governor_score=82.7.

### MC.PA — OBSERVE_SHADOW
SHADOW_ONLY governor for MC.PA: PDC=OBSERVE (v1=WATCH), PCE=NORMAL_PULLBACK (score=63.3), combined_rank=1.45 → OBSERVE (OBSERVE_SHADOW). Alignment=ALIGNED, governor_score=55.6.

### SIE.DE — WATCH_SHADOW
SHADOW_ONLY governor for SIE.DE: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=70.3), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=61.6. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### AAPL — WATCH_SHADOW
SHADOW_ONLY governor for AAPL: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=65.4), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=59.2. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### QQQ — WATCH_SHADOW
SHADOW_ONLY governor for QQQ: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=55.7), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=46.9. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### LLY — TRAIL_SHADOW
SHADOW_ONLY governor for LLY: PDC=TRAIL_PROTECT_SHADOW (v1=EXIT_PROTECT_SHADOW), PCE=NORMAL_PULLBACK (score=63.6), combined_rank=2.55 → TRAIL_PROTECT_SHADOW (TRAIL_SHADOW). Alignment=ALIGNED, governor_score=31.8. Profit-at-risk rule active; Profit lock active.

Notes: Profit-at-risk rule active; Profit lock active

### HSBA.L — TRAIL_SHADOW
SHADOW_ONLY governor for HSBA.L: PDC=WATCH (v1=WATCH), PCE=PROTECT_NOW (score=49.7), combined_rank=3.35 → TRAIL_PROTECT_SHADOW (TRAIL_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=24.9. Profit-at-risk rule active; Profit lock active; Safety: PnL ≤ 0 with large prior peak — cannot keep winner posture; Context escalates committee (WATCH → TRAIL_PROTECT_SHADOW).

Notes: Profit-at-risk rule active; Profit lock active; Safety: PnL ≤ 0 with large prior peak — cannot keep winner posture; Context escalates committee (WATCH → TRAIL_PROTECT_SHADOW)

### AMAT — PROTECT_SHADOW
SHADOW_ONLY governor for AMAT: PDC=PARTIAL_PROTECT_SHADOW (v1=EXIT_PROTECT_SHADOW), PCE=CONTEXT_WEAKENING (score=49.7), combined_rank=3.55 → PARTIAL_PROTECT_SHADOW (PROTECT_SHADOW). Alignment=ALIGNED, governor_score=24.9. Profit-at-risk rule active; Profit lock active.

Notes: Profit-at-risk rule active; Profit lock active

### MU — PROTECT_SHADOW
SHADOW_ONLY governor for MU: PDC=PARTIAL_PROTECT_SHADOW (v1=EXIT_PROTECT_SHADOW), PCE=CONTEXT_WEAKENING (score=49.7), combined_rank=3.55 → PARTIAL_PROTECT_SHADOW (PROTECT_SHADOW). Alignment=ALIGNED, governor_score=24.9. Profit-at-risk rule active; Profit lock active.

Notes: Profit-at-risk rule active; Profit lock active

