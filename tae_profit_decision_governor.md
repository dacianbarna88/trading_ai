# TAE Profit Decision Governor v1

**Generated:** 2026-09-03T16:01:32
**Mode:** SHADOW_ONLY — NONE
**Final verdict:** PDG_SHADOW_READY_FOR_OBSERVATION

> **NO BUY / NO SELL — SHADOW_ONLY profit decision VIEW**

Profit protect pipeline VIEW — reconciles PDC + PCE; live execution remains live_bot.py

## Executive summary

- **Overall profit posture:** NOT_READY
- **Validation readiness:** UNKNOWN
- **Committee verdict:** PDC_SHADOW_READY_FOR_OBSERVATION
- **Context verdict:** PCE_SHADOW_READY_FOR_OBSERVATION
- **Total tickers:** 22
- **Average governor score:** 61.5

## Sources loaded

- ✅ tae_profit_committee_learning.json
- ✅ tae_profit_context_engine.json
- ✅ tae_profit_context_learning.json
- ✅ tae_profit_decision_committee.json
- ✅ tae_profit_intelligence_brain.json
- ✅ tae_profit_memory_engine.json
- ❌ tae_profit_protection_shadow.json
- ❌ tae_profit_protection_validation.json

## Posture counts

- **INSUFFICIENT_DATA:** 0
- **KEEP_WINNER_SHADOW:** 0
- **OBSERVE_SHADOW:** 14
- **PROTECT_SHADOW:** 0
- **TRAIL_SHADOW:** 0
- **WATCH_SHADOW:** 8

## Alignment counts

- **CONTEXT_ESCALATES:** 22

## Blocker summary

- **SHADOW_ONLY** — No live or advisory integration — observation VIEW only [tae_profit_decision_governor.py]

## Top 5 PROTECT_SHADOW

| ticker | governor score | final rec | alignment |
| --- | --- | --- | --- |

## Top 5 KEEP_WINNER_SHADOW

| ticker | governor score | final rec | PCE verdict |
| --- | --- | --- | --- |

## Per-ticker governor view

| ticker | governor score | posture | final rec | PDC weighted | PCE verdict | alignment | conf |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALV.DE | 82.2 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| NVDA | 76.3 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| SAP.DE | 74.8 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| AAPL | 71.3 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| SPY | 70.0 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| ABBV | 67.6 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| PG | 67.6 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| MRK | 64.0 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| PM | 64.0 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| DIA | 62.6 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| LLY | 62.6 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| GE | 55.4 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| HD | 55.4 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| AMAT | 52.2 | OBSERVE_SHADOW | OBSERVE | HOLD | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| ULVR.L | 62.1 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| SHEL.L | 58.6 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| AIR.PA | 52.2 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| MC.PA | 52.2 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| SIE.DE | 52.2 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| HSBA.L | 52.1 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| QQQ | 49.9 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |
| MU | 48.6 | WATCH_SHADOW | WATCH | OBSERVE | CONTEXT_WEAKENING | CONTEXT_ESCALATES | MEDIUM |

## Per-ticker explanations

### ALV.DE — OBSERVE_SHADOW
SHADOW_ONLY governor for ALV.DE: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=86.5), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=82.2. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### NVDA — OBSERVE_SHADOW
SHADOW_ONLY governor for NVDA: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=74.7), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=76.3. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### SAP.DE — OBSERVE_SHADOW
SHADOW_ONLY governor for SAP.DE: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=86.5), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=74.8. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### AAPL — OBSERVE_SHADOW
SHADOW_ONLY governor for AAPL: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=74.7), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=71.3. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### SPY — OBSERVE_SHADOW
SHADOW_ONLY governor for SPY: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=71.9), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=70.0. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### ABBV — OBSERVE_SHADOW
SHADOW_ONLY governor for ABBV: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=72.2), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=67.6. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### PG — OBSERVE_SHADOW
SHADOW_ONLY governor for PG: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=72.2), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=67.6. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### MRK — OBSERVE_SHADOW
SHADOW_ONLY governor for MRK: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=65.1), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=64.0. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### PM — OBSERVE_SHADOW
SHADOW_ONLY governor for PM: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=65.1), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=64.0. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### DIA — OBSERVE_SHADOW
SHADOW_ONLY governor for DIA: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=62.3), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=62.6. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### LLY — OBSERVE_SHADOW
SHADOW_ONLY governor for LLY: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=57.2), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=62.6. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### GE — OBSERVE_SHADOW
SHADOW_ONLY governor for GE: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=47.7), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=55.4. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### HD — OBSERVE_SHADOW
SHADOW_ONLY governor for HD: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=47.7), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=55.4. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### AMAT — OBSERVE_SHADOW
SHADOW_ONLY governor for AMAT: PDC=HOLD (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=56.5), combined_rank=1.35 → OBSERVE (OBSERVE_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=52.2. Context escalates committee (HOLD → OBSERVE).

Notes: Context escalates committee (HOLD → OBSERVE)

### ULVR.L — WATCH_SHADOW
SHADOW_ONLY governor for ULVR.L: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=71.3), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=62.1. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### SHEL.L — WATCH_SHADOW
SHADOW_ONLY governor for SHEL.L: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=64.2), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=58.6. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### AIR.PA — WATCH_SHADOW
SHADOW_ONLY governor for AIR.PA: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=51.5), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=52.2. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### MC.PA — WATCH_SHADOW
SHADOW_ONLY governor for MC.PA: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=51.5), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=52.2. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### SIE.DE — WATCH_SHADOW
SHADOW_ONLY governor for SIE.DE: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=51.5), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=52.2. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### HSBA.L — WATCH_SHADOW
SHADOW_ONLY governor for HSBA.L: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=71.3), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=52.1. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### QQQ — WATCH_SHADOW
SHADOW_ONLY governor for QQQ: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=46.8), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=49.9. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

### MU — WATCH_SHADOW
SHADOW_ONLY governor for MU: PDC=OBSERVE (v1=NO_ACTION), PCE=CONTEXT_WEAKENING (score=64.2), combined_rank=1.90 → WATCH (WATCH_SHADOW). Alignment=CONTEXT_ESCALATES, governor_score=48.6. Context escalates committee (OBSERVE → WATCH).

Notes: Context escalates committee (OBSERVE → WATCH)

