# TAE Profit Decision Governor v1 — Implementation Report

**Date:** 2026-07-06  
**Mode:** SHADOW_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE  
**Status:** **PASS**

---

## Summary

Implemented the missing **Profit Decision Governor (PDG v1)** as a read-only materialized VIEW that reconciles PDC weighted committee output with PCE adaptive context into a single shadow profit decision per ticker. Wired into `python3 tae.py protect` as the final pipeline step after PCE.

---

## Architecture

```
Profit Protection Shadow
        ↓
Profit Intelligence Brain (PSP)
        ↓
Profit Memory Engine
        ↓
Profit Decision Committee (v2 weighted)
        ↓
Committee Learning
        ↓
Profit Context Engine (v2 adaptive)
        ↓
Profit Decision Governor (v1) ← NEW
```

PDG reads upstream JSON only — it does **not** re-run analysis engines.

---

## Governor Model

### Reconciliation

```
combined_rank = PDC_weighted_rank × 0.55 + PCE_context_rank × 0.45
governor_score = context_score × 0.5 + (100 − protection_score) × 0.5
```

| Signal | Higher value means |
|--------|-------------------|
| PDC protection_score | More protect pressure |
| PCE profit_context_score | Stronger keep-winner context |
| governor_score | Net keep-winner conviction (0–100) |

### Governor postures

| Posture | Meaning |
|---------|---------|
| `KEEP_WINNER_SHADOW` | PDC + PCE aligned to hold |
| `TRAIL_SHADOW` | Moderate protect / trail shadow |
| `PROTECT_SHADOW` | Partial or exit protect shadow |
| `WATCH_SHADOW` | Observe closely |
| `OBSERVE_SHADOW` | Low urgency observation |
| `INSUFFICIENT_DATA` | Missing upstream data |

### Alignment labels

- **ALIGNED** — PDC and PCE within 1 rank step
- **CONTEXT_SOFTENS** — PCE reduces protect urgency vs PDC
- **CONTEXT_ESCALATES** — PCE increases protect urgency vs PDC

### Safety rules

- `current_pct ≤ 0` and `high_pct ≥ 4%` → cannot be `KEEP_WINNER_SHADOW`
- Profit-at-risk rule active → minimum `WATCH`

---

## Inputs (read-only)

| Source | Used for |
|--------|----------|
| `tae_profit_decision_committee.json` | PDC v1 + weighted rec |
| `tae_profit_context_engine.json` | PCE verdict + score |
| `tae_profit_protection_shadow.json` | Rules v1 safety |
| `tae_profit_committee_learning.json` | Member weights |
| `tae_profit_context_learning.json` | Context weights |
| `tae_profit_protection_validation.json` | Readiness / blockers |
| `tae_profit_intelligence_brain.json` | Source attribution |
| `tae_profit_memory_engine.json` | Source attribution |

---

## Sample Ticker Explanations

### MRK — KEEP_WINNER_SHADOW (94.7)

PDC=HOLD, PCE=KEEP_WINNER → aligned HOLD. Governor score 94.7.

### AMAT — PROTECT_SHADOW (25.2)

PDC=PARTIAL_PROTECT_SHADOW, PCE=CONTEXT_WEAKENING → aligned PARTIAL_PROTECT_SHADOW. Context no longer hard-zeros but protect pressure remains.

### HSBA.L — TRAIL_SHADOW (25.2)

PDC=WATCH, PCE=PROTECT_NOW → context escalates to TRAIL_PROTECT_SHADOW. Safety: PnL ≤ 0 with large prior peak.

---

## Validation Run

```
python3 tae_profit_decision_governor.py   # PASS
python3 tae.py protect                    # PASS (7 steps)
FORBIDDEN_IMPORTS: []                     # PASS
```

### Global summary (12 tickers)

| Metric | Value |
|--------|-------|
| Final verdict | PDG_SHADOW_READY_FOR_OBSERVATION |
| Overall posture | WATCH |
| Avg governor score | 57.4 |
| KEEP_WINNER_SHADOW | 4 |
| TRAIL_SHADOW | 2 |
| PROTECT_SHADOW | 2 |
| WATCH_SHADOW | 3 |
| ALIGNED | 8 |
| CONTEXT_ESCALATES | 4 |

---

## Files Created / Modified

| File | Change |
|------|--------|
| `tae_profit_decision_governor.py` | New governor composer |
| `tae_profit_decision_governor.json` / `.md` | Outputs |
| `tae_cli/commands/protect.py` | PDG step + summary |
| `TAE_PROFIT_DECISION_GOVERNOR_V1_REPORT.md` | This report |

**Not modified:** `live_bot.py`, `core/trades.py`, `portfolio.csv`, broker/execution

---

## Live Execution Confirmation

| Check | Status |
|-------|--------|
| BUY/SELL executed | **NO** |
| `live_trading_impact` | `NONE` |
| Broker touched | **NO** |
| Commit | **NO** |

---

## Overall Verdict

**PASS** — PDG v1 operational. Profit protect pipeline now runs through governor materialization with explainable PDC+PCE reconciliation.
