# TAE Profit Target Adapter V1 — Sprint Report

**Sprint:** X.PROFIT-GROWTH-5 — Dynamic Profit Target Adapter  
**Date:** 2026-07-07  
**Base checkpoint:** `655e439` — TAE Growth 4: add growth intelligence integrator  
**Pre-build audit:** `TAE_DPTI_PREBUILD_AUDIT.md` — EXTEND + SMALL ADAPTER  
**Mode:** SHADOW_ONLY · READ_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE · NO_ADVISORY_CHANGE · NO_COMMIT  
**Status:** **PASS**

---

## Summary

Created a small **Dynamic Profit Target Adapter** that converts existing Growth Intelligence into per-ticker numeric shadow target guidance. Not a simulator, not a new engine, no upstream recompute.

---

## Files created

| File | Role |
|------|------|
| `tae_profit_target_adapter.py` | Adapter engine (stdlib only) |
| `tae_profit_target_adapter.json` | Structured target output |
| `tae_profit_target_adapter.md` | Human-readable report |
| `tae_cli/commands/profit_targets.py` | CLI command |
| `TAE_PROFIT_TARGET_ADAPTER_V1_REPORT.md` | This report |

**Modified (CLI only):** `tae_cli/dispatcher.py`, `tae_cli/commands/help.py`

**Not modified:** Upstream engines, `live_bot.py`, `core/`, `portfolio.csv`, advisory modules

---

## Inputs reused (read-only)

| Source | Role |
|--------|------|
| `tae_growth_intelligence.json` | Primary — scores, strategies, lifecycle fields |
| `tae_profit_protection_shadow.json` | Baseline anchors (6/8/10%, lock 4%, trailing 1/1.5%) |
| `tae_winner_lifecycle_profiler.json` | Fallback if GII missing |
| `tae_opportunity_cost_ledger.json` | Loaded for context |
| `tae_profit_protection_validation.json` | Trailing bias from best shadow method |
| `tae_profit_growth_analytics.json` | Capture rate for improvement hint |
| `tae_adaptive_profit_policy_engine.json` | Portfolio policy bias |
| `tae_profit_decision_governor.json` | Context flag |
| `tae_accounting_snapshot.json` | Context flag |

---

## Anti-duplication statement

Per `TAE_DPTI_PREBUILD_AUDIT.md`:

- **Does not** recompute growth_score, lifecycle_stage, opportunity categories, capture rate, PSP, or shadow PnL simulation  
- **Does** translate GII `recommended_shadow_strategy` + baselines into numeric targets  
- **Anchors** to shadow `rules_v1_config` static levels; adjusts ± per strategy rules  

---

## Target adaptation model

| Strategy | Adaptation |
|----------|------------|
| KEEP_GROWING_SHADOW | +1.5% partial TP, +0.25% trailing, +0.5% lock, LOW urgency, 20% partial |
| HOLD_AND_MONITOR_SHADOW | Neutral baselines, MEDIUM urgency |
| PROTECT_PROFIT_SHADOW | −1.5% partial TP, −0.25% trailing, 33% partial, HIGH urgency |
| TIGHTEN_TRAIL_SHADOW | −1% partial, −0.35% trailing, −0.75% lock, HIGH urgency |
| REDUCE_EXPOSURE_SHADOW | −2% partial, −0.5% trailing, 50% partial, CRITICAL |
| COLLAPSED | No growth target — recovery/exit only (`dynamic_partial_tp_pct`: null) |

Portfolio bias: APPE `TIGHTEN_TRAILING` / HIGH_RISK tightens trailing; validation best-method adds trailing bias.

---

## Sample output

| Metric | Value |
|--------|-------|
| Global verdict | `PROFIT_TARGET_ADAPTER_READY` |
| Dominant mode | KEEP_GROWING_SHADOW (4 tickers) |
| Portfolio policy | CAPITAL_PRESERVATION_SHADOW |
| Avg partial TP | 5.91% (baseline 6%) |
| Avg trailing | 0.95% (baseline 1.0%) |
| Avg profit lock | 4.0% |

**Keep-growing:** MRK, PG, PM, SPY → partial TP **7.5%**, trailing **1.2%**, urgency LOW

**Protection:** AMAT, MU → partial TP **3.5%**, trailing **0.6%**, urgency CRITICAL

**Collapsed:** HSBA.L → no growth partial target, 50% partial size, CRITICAL urgency

**Capture hint:** 29.1% capture with $830 missed — earlier partial TP on high-opportunity tickers (shadow hypothesis)

---

## Validation

```bash
python3 tae_profit_target_adapter.py          # PASS
python3 tae.py profit-targets                 # PASS
python3 tae.py help                           # PASS (includes profit-targets)
FORBIDDEN_IMPORTS: []                         # PASS
```

---

## Recommended next sprint

```text
X.PROFIT-GROWTH-6 — Profit Target Policy Learning
```

Persist target adapter outputs across runs and learn which dynamic adjustments correlate with improved capture (shadow only).

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

**PASS** — Dynamic Profit Target Adapter V1 operational. Closes the ~32% gap identified in DPTI pre-build audit without duplicating upstream engines.
