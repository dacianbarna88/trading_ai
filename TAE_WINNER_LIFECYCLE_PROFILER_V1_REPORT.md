# TAE Winner Lifecycle Profiler V1 — Sprint Report

**Sprint:** X.PROFIT-GROWTH-3 — Winner Lifecycle Profiler  
**Date:** 2026-07-06  
**Base checkpoint:** `2d46a35` — Growth Analytics SSOT  
**Prior sprint:** Opportunity Cost Ledger — PASS  
**Mode:** SHADOW_ONLY · READ_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE · NO_ADVISORY_CHANGE · NO_COMMIT  
**Status:** **PASS**

---

## Summary

Built the first **Winner Lifecycle Profiler** — a read-only research layer modeling how winners are born, grow, weaken, and die. Not a protection engine. Joins growth analytics, opportunity ledger, memory, context, governor, and validation SSOT inputs.

---

## Files created

| File | Role |
|------|------|
| `tae_winner_lifecycle_profiler.py` | Lifecycle engine (stdlib only) |
| `tae_winner_lifecycle_profiler.json` | Structured profiler output |
| `tae_winner_lifecycle_profiler.md` | Human-readable report |
| `tae_cli/commands/winner.py` | CLI command |
| `TAE_WINNER_LIFECYCLE_PROFILER_V1_REPORT.md` | This report |

**Modified (CLI only):** `tae_cli/dispatcher.py`, `tae_cli/commands/help.py`

**Not modified:** `live_bot.py`, `core/`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt`

---

## Lifecycle model

### Stages (9)

DISCOVERY · EARLY_WINNER · MATURE_WINNER · PEAK_WINNER · WEAKENING · PROFIT_DECAY · COLLAPSED · SURVIVED · UNKNOWN

### Per-ticker fields

`ticker`, `current_pct`, `highest_pct`, `drawdown_pct`, `missed_usd`, `profit_age_days`, `growth_velocity`, `profit_decay_velocity`, `lifecycle_stage`, `lifecycle_score`, `collapse_probability`, `survival_probability`, `optimal_shadow_action`, `confidence`, `explanation`

### Shadow actions (no execution)

KEEP · WATCH · PARTIAL_PROTECT · TRAIL · PROTECT · EXIT · UNKNOWN

### Classification priority

1. COLLAPSED — current ≤ 0% after peak > 6%  
2. PROFIT_DECAY — drawdown > 5% or memory collapse with high peak  
3. WEAKENING — drawdown > 2%  
4. SURVIVED — peak ≈ current with profit retained  
5. PEAK / MATURE / EARLY — by current % bands  
6. DISCOVERY — peak < 1%  

### Probability & score

- **Collapse probability (0–1):** memory giveback risk, PCE verdict, growth status, ledger category, validation, drawdown, missed USD, stage  
- **Survival probability (0–1):** memory PSP survival, PCE/trend context, drawdown, stage  
- **Lifecycle score (0–100):** stage base + peak retention + survival − collapse penalty  

---

## Statistics (live run)

| Metric | Value |
|--------|-------|
| Global verdict | `LIFECYCLE_PROFILER_READY` |
| Tickers profiled | 12 |
| Portfolio lifecycle score | **43.8** / 100 |
| Average lifecycle score | 52.0 |
| Average survival | 0.517 |
| Average collapse | 0.524 |
| Healthy winners | 8 |
| Weakening | 1 |
| Collapsing (PROFIT_DECAY) | 2 |
| Collapsed | 1 |
| Survived | 2 |

### Lifecycle distribution

| Stage | Count |
|-------|-------|
| SURVIVED | 2 |
| EARLY_WINNER | 3 |
| DISCOVERY | 3 |
| WEAKENING | 1 |
| PROFIT_DECAY | 2 |
| COLLAPSED | 1 |

### Top collapse candidates

| Ticker | Stage | Collapse | Action |
|--------|-------|----------|--------|
| HSBA.L | COLLAPSED | 1.00 | EXIT |
| MU | PROFIT_DECAY | 1.00 | PARTIAL_PROTECT |
| AMAT | PROFIT_DECAY | 1.00 | PARTIAL_PROTECT |

### Top survivors

MRK, PG (SURVIVED, score 100), PM, SPY (EARLY_WINNER, high survival)

---

## Validation

```bash
python3 tae_winner_lifecycle_profiler.py          # PASS
python3 tae.py winner                             # PASS
python3 tae.py help                               # PASS (includes winner)
FORBIDDEN_IMPORTS: []                             # PASS
```

---

## Recommended next sprint

```text
X.PROFIT-GROWTH-4 — Dynamic Profit Target Optimizer
```

Use lifecycle stage + collapse probability to suggest dynamic profit targets per ticker (shadow only).

---

## Confirmations

| Rule | Status |
|------|--------|
| SHADOW_ONLY | ✅ |
| READ_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_EXECUTION | ✅ |
| NO_PORTFOLIO_CHANGE | ✅ |
| NO_LIVE_BOT_CHANGE | ✅ |
| NO_ADVISORY_CHANGE | ✅ |
| NO_COMMIT | ✅ |

---

## Overall verdict

**PASS** — Winner Lifecycle Profiler V1 operational. First research layer explaining winner birth, growth, weakening, and death across the portfolio.
