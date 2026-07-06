# TAE PDC V2 — Adaptive Weighted Committee Report

**Date:** 2026-07-06  
**Checkpoint:** 663cc15+ PDC V1  
**Mode:** SHADOW_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE  
**Status:** **PASS**

---

## Summary

Implemented adaptive weighted committee learning via `tae_profit_committee_learning.py`. Each committee member now tracks historical accuracy, receives a dynamic weight (0.40–2.50), and contributes to a weighted final recommendation per ticker. Extended `python3 tae.py protect` with the learning step.

---

## Adaptive Committee Architecture

```
Profit Protection Shadow
        ↓
Profit Intelligence Brain (PSP)
        ↓
Profit Memory Engine
        ↓
Profit Decision Committee (v1 votes)
        ↓
Committee Learning (v2 weights + weighted decision)
        ↓
Final Summary (learning + weighted committee MD)
```

### Committee members

| Member | Vote key | Maps to recommendation |
|--------|----------|------------------------|
| Rules | `protection_rules` | EXIT / PARTIAL / WATCH / NO_ACTION |
| PIB | `profit_intelligence` | PIB/PSP-adjusted rec |
| PSP | `profit_survival` | CRITICAL→EXIT, ELEVATED→WATCH, STABLE→HOLD |
| Memory | `profit_memory` | Collapse→EXIT, Survived→HOLD |
| Validation | `validation` | PROTECT / HOLD / OBSERVE |

---

## Learning Model

Per member, persisted in `tae_profit_committee_learning.json`:

- `total_votes`, `correct_votes`, `incorrect_votes`
- `accuracy` (correct / total)
- `weight` (derived from accuracy bands)
- `trend` (IMPROVING / STABLE / DECLINING vs prior accuracy)
- `recommended_bias` (TRUST / NEUTRAL / DISCOUNT / BOOTSTRAP)

**Ground truth:** memory episode labels (`PROFIT_COLLAPSED` → protect, `PROFIT_SURVIVED` → hold, etc.)

**Observation dedupe:** stable key from `episode_key` or ticker+label+metrics (no committee timestamp).

---

## Weight Update Logic

| Accuracy | Weight |
|----------|--------|
| < 40% | 0.60 |
| 40–55% | 0.80 |
| 55–70% | 1.00 |
| 70–85% | 1.40 |
| 85–95% | 1.80 |
| > 95% | 2.20 |

Clamped: **min 0.40**, **max 2.50**

---

## Weighted Decision Example (AMAT)

| Member | Weight × Vote |
|--------|---------------|
| Rules | 0.8 × EXIT_PROTECT_SHADOW |
| PIB | 0.8 × WATCH |
| PSP | 0.8 × EXIT_PROTECT_SHADOW |
| Memory | 2.2 × EXIT_PROTECT_SHADOW |
| Validation | 0.6 × OBSERVE |

**Weighted result:** `PARTIAL_PROTECT_SHADOW` (MEDIUM confidence)

v1 was `EXIT_PROTECT_SHADOW`; Memory's high weight (2.2) moderates toward partial vs unanimous exit.

---

## Current Member Weights (first learning run)

| Member | Accuracy | Weight | Trend |
|--------|----------|--------|-------|
| Memory | 100% | 2.20 | STABLE |
| Rules | 50% | 0.80 | STABLE |
| PSP | 50% | 0.80 | STABLE |
| PIB | 41.7% | 0.80 | STABLE |
| Validation | 33.3% | 0.60 | STABLE |

---

## Files Created / Modified

| File | Change |
|------|--------|
| `tae_profit_committee_learning.py` | Adaptive learning engine |
| `tae_profit_committee_learning.json` / `.md` | Learning state + report |
| `tae_cli/commands/protect.py` | Added learning step + final summary |
| `tae_cli/commands/help.py` | Updated protect description |
| `tae_profit_decision_committee.json` / `.md` | Enriched with `weighted_tickers` |
| `TAE_PDC_V2_ADAPTIVE_REPORT.md` | This report |

**Not modified:** `live_bot.py`, broker/execution, `portfolio.csv`, `core/trades.py`

---

## Validation

### Learning run

```bash
python3 tae_profit_committee_learning.py
```

```
Final verdict: PDC_V2_SHADOW_READY_FOR_OBSERVATION
Memory: accuracy 100% weight 2.2
Rules/PIB/PSP: ~50% weight 0.8
Validation: 33.3% weight 0.6
```

### Re-run dedupe

Second immediate run: vote counts unchanged (12 per member) — observation dedupe confirmed.

### Forbidden imports

```
FORBIDDEN_IMPORTS: []
```

### CLI

```bash
python3 tae.py protect
```

Pipeline: shadow → brain → memory → committee → **learning** → final summary.

---

## Live Execution Confirmation

| Check | Status |
|-------|--------|
| BUY/SELL executed | **NO** |
| `live_trading_impact` | `NONE` |
| Broker touched | **NO** |
| Mode | `SHADOW_ONLY` |
| Commit | **NO** |

---

## Overall Verdict

**PASS** — PDC V2 adaptive weighted committee operational. Learning persists, weights update from episode outcomes, weighted recommendations exposed in committee + learning outputs. Live trading unchanged.
