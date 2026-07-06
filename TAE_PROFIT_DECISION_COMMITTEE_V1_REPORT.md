# TAE Profit Decision Committee v1 — Implementation Report

**Date:** 2026-07-06  
**Checkpoint:** 663cc15 — TAE PIB V3  
**Mode:** SHADOW_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE  
**Status:** **PASS**

---

## Summary

Built `tae_profit_decision_committee.py` — a shadow-only committee that consolidates profit protection rules, PIB/PSP, profit memory, and validation into one scored recommendation per ticker. Exposed via `python3 tae.py protect`.

---

## Committee Model

### Input sources (read-only)

| Source | Data used |
|--------|-----------|
| `tae_profit_protection_shadow.json` | Rules v1, protection signals |
| `tae_profit_intelligence_brain.json` | PIB votes, PSP metrics, adjusted rec |
| `tae_profit_memory_engine.json` | Episode labels, ticker memory bias |
| `tae_profit_protection_validation.json` | Per-ticker validation recommendations |

### Committee votes (per ticker)

| Vote | Source |
|------|--------|
| `protection_rules` | Shadow rules v1 / protection signal |
| `profit_intelligence` | PIB / PSP-adjusted recommendation |
| `profit_survival` | PSP urgency, giveback, survival |
| `profit_memory` | Memory bias + latest episode label |
| `validation` | Historical validation per ticker |

### Output fields

- `protection_score` (0–100)
- `confidence` (LOW / MEDIUM / HIGH)
- `committee_votes`
- `final_committee_recommendation`
- `explanation`

### Allowed recommendations

`HOLD` · `OBSERVE` · `WATCH` · `TRAIL_PROTECT_SHADOW` · `PARTIAL_PROTECT_SHADOW` · `EXIT_PROTECT_SHADOW` · `NO_ACTION`

---

## Scoring Logic

**Base score:** 35

| Factor | Score impact |
|--------|--------------|
| Profit at risk (rules v1) | +15 |
| Episode collapsed | +20 |
| Episode decayed | +12 |
| PSP giveback ≥ 0.75 | +15 |
| PSP survival ≤ 0.20 | +12 |
| PSP CRITICAL urgency | +10 |
| MEMORY_PROTECT_EARLY | +15 |
| High missed USD / peak fade | +4 to +10 |
| MEMORY_HOLD_WINNERS | −15 |
| Episode survived | −10 |
| PSP survival ≥ 0.80 | −12 |
| Stable trend + profit | −15 |

### Score bands

| Score | Recommendation |
|-------|----------------|
| 0–20 | NO_ACTION |
| 21–40 | OBSERVE |
| 41–60 | WATCH |
| 61–80 | PARTIAL_PROTECT_SHADOW |
| 81–100 | EXIT_PROTECT_SHADOW |

### Overrides

- **HOLD:** high survival + stable profit + memory hold bias
- **TRAIL_PROTECT_SHADOW:** mid-score with trailing protection signal
- **Safety (PnL ≤ 0):** blocks PARTIAL/EXIT/TRAIL → WATCH if significant fade, else NO_ACTION

---

## CLI Protect Behavior

```bash
python3 tae.py protect
```

Runs pipeline in order:

1. `tae_profit_protection_shadow.py`
2. `tae_profit_intelligence_brain.py`
3. `tae_profit_memory_engine.py`
4. `tae_profit_decision_committee.py`

Prints concise summary from `tae_profit_decision_committee.md` (first 40 lines).

**CLI constraints:** stdlib only in CLI modules — no `research_core`, no `pandas`.

### Files modified for CLI

| File | Change |
|------|--------|
| `tae_cli/commands/protect.py` | New protect pipeline command |
| `tae_cli/dispatcher.py` | Register `protect` |
| `tae_cli/commands/help.py` | Add protect to help banner |

---

## Validation Output

### Committee direct run

```
Final verdict: PDC_SHADOW_READY_FOR_OBSERVATION
Tickers: 12
Avg protection score: 49.4
Critical / watch / hold+no_action: 3 / 2 / 7
```

### Forbidden imports

```
FORBIDDEN_IMPORTS: []
```

### `python3 tae.py protect`

Pipeline completed exit 0; printed committee MD summary.

### Protected files

| File | Changed |
|------|---------|
| `live_bot.py` | **NO** |
| `core/trades.py` | **NO** |
| `portfolio.csv` | **NO** |

---

## Sample Recommendations

### AMAT — EXIT_PROTECT_SHADOW (score 100)

Collapsed episode, PSP critical, rules urgent — exit protection advisory (shadow only).

### HSBA.L — WATCH (score 100)

Same high score but **PnL ≤ 0** → safety override downgrades to WATCH despite collapse signals.

### MRK — HOLD (score 0)

Episode survived, PSP stable, PIB hold — committee confirms HOLD.

### LLY — EXIT_PROTECT_SHADOW (score 100)

Positive PnL (+2.69%), PSP critical, PIB exit — partial/exit band applies.

---

## Global Summary (current run)

| Metric | Value |
|--------|-------|
| Total tickers | 12 |
| Avg protection score | 49.4 |
| Critical (partial/exit) | 3 |
| Watch/observe/trail | 2 |
| Hold / no action | 7 |
| Final verdict | `PDC_SHADOW_READY_FOR_OBSERVATION` |

---

## Live Execution Confirmation

| Check | Status |
|-------|--------|
| BUY/SELL executed | **NO** |
| `live_trading_impact` | `NONE` |
| Broker touched | **NO** |
| Mode | `SHADOW_ONLY` |

---

## Overall Verdict

**PASS** — Profit Decision Committee v1 and `tae.py protect` implemented and validated. Live trading unchanged.
