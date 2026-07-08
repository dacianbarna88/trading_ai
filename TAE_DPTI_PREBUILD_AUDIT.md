# TAE DPTI Pre-Build Audit — Dynamic Profit Target Intelligence Anti-Duplication

**Sprint:** X.PROFIT-GROWTH-5 PRE-AUDIT  
**Date:** 2026-07-07  
**Base checkpoint:** `655e439` — TAE Growth 4: add growth intelligence integrator  
**Mode:** READ_ONLY · NO_BROKER · NO_EXECUTION · NO_PORTFOLIO_CHANGE · NO_LIVE_BOT_CHANGE · NO_ADVISORY_CHANGE · NO_COMMIT  
**DPTI engine created:** **NO** (audit only)

---

## Executive verdict

**Recommendation: EXTEND EXISTING PROFIT / GROWTH STACK + BUILD SMALL ADAPTER**

Estimated coverage of DPTI intent by existing modules: **~68%** (building blocks and static rules) with **~32% true gap** (unified per-ticker *dynamic* profit target SSOT).

Do **not** build a new independent trading or protection engine. Build a thin **SHADOW_ONLY read-only adapter** that:

1. Reads Growth Intelligence + Lifecycle + Shadow + Validation JSON outputs  
2. Emits per-ticker **numeric** dynamic targets (partial TP %, trailing %, hold ceiling, exit urgency)  
3. Does **not** re-run fade simulation, PSP, capture-rate math, or lifecycle classification  

---

## Phase 0 search commands run

```bash
find . -maxdepth 2 -type f | egrep -i "target|profit|trailing|exit|optimizer|threshold|capture|winner|growth" | sort
grep -RniE "profit target|take profit|partial|trailing|exit window|dynamic target|target optimizer|sell threshold|capture rate|hold optimization" . \
  --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__ \
  --exclude="*.csv" --exclude="*.json" | head -300
```

**Key finding:** No file named `*dynamic*target*`, `*profit_target*`, `*target_optimizer*`, or `tae_dpti*` exists. Closest matches are the Profit Growth stack (GA → ledger → lifecycle → GII) and the Protection shadow/validation pair with **fixed** thresholds.

---

## Existing target / profit / exit functionality found

### Profit Growth stack (analytics + integration — no numeric targets)

| Module | What it computes | Classification |
|--------|------------------|----------------|
| `tae_profit_growth_analytics.py` | Capture rate, missed USD, growth_status | **EXISTS_CAN_REUSE** (inputs) |
| `tae_opportunity_cost_ledger.py` | Why profit missed; maps to fixes e.g. `TEST_PARTIAL_TP_AT_DYNAMIC_THRESHOLD` | **EXISTS_CAN_REUSE** (inputs); fix names only, no dynamic % |
| `tae_winner_lifecycle_profiler.py` | Lifecycle stage, collapse/survival, `optimal_shadow_action` (KEEP/TRAIL/EXIT) | **PARTIAL_OVERLAP** — qualitative action, not numeric target |
| `tae_growth_intelligence.py` | Composite scores, `recommended_shadow_strategy`, `future_growth_potential` | **EXISTS_CAN_REUSE** (primary DPTI input SSOT) |

### Protection stack (static thresholds + shadow simulation)

| Module | What it computes | Classification |
|--------|------------------|----------------|
| `tae_profit_protection_shadow.py` | **Fixed** partial TP: 6% / 8% / 10%; profit lock 4%; fade alert 1.5%; shadow actions `TEST_SELL_20/30`, `TEST_TRAILING_1/1_5`; per-position estimated protected USD | **EXISTS_CAN_REUSE** — canonical static rules + counterfactual estimates |
| `tae_profit_protection_validation.py` | Compares shadow strategies on fade history; portfolio best strategy (`shadow_trailing_1`, etc.); promotes `TEST_TRAILING_SHADOW` / `TEST_PARTIAL_SELL_SHADOW` | **EXISTS_CAN_REUSE** — validation layer, not per-ticker dynamic tuning |
| `tae_profit_intelligence_brain.py` | PSP survival/giveback; `PARTIAL_PROTECT_SHADOW`, `EXIT_PROTECT_SHADOW`, `TRAIL_PROTECT_SHADOW` | **EXISTS_CAN_REUSE** (urgency inputs); **not** profit target % |
| `tae_profit_decision_governor.py` | Rank thresholds → posture recommendations | **EXISTS_CAN_REUSE** (governor posture) |
| `tae_portfolio_profit_governor.py` | Portfolio verdict, quality score | **EXISTS_CAN_REUSE** (portfolio context) |
| `tae_adaptive_profit_policy_engine.py` | Policy state; e.g. `TIGHTEN_TRAILING_SHADOW` | **EXISTS_CAN_REUSE** (policy bias) |

### Live / core execution (must not touch)

| Module | What it computes | Classification |
|--------|------------------|----------------|
| `core/trailing.py` | Live trailing activate 4% / distance 5%; executes sell trigger | **DO NOT BUILD / DO NOT TOUCH** |
| `core/exit_intelligence.py` | Score-based exit points (entry signal decay) | **PARTIAL_OVERLAP** — exit scoring, not profit targets |
| `live_bot.py` (forbidden) | TAKE PROFIT signal, trailing integration | **DO NOT TOUCH** |

### Threshold / optimizer ecosystem (entry domain — not profit targets)

| Module | What it computes | Classification |
|--------|------------------|----------------|
| `threshold_*`, `intelligence/threshold_*` | BUY score thresholds (80/90), virtual candidates | **LEGACY** / **PARTIAL_OVERLAP** — entry gate, not take-profit |
| `threshold_test_simulator.py` | Score ≥90/80 candidate lists | **LEGACY** |
| `confidence_optimizer_engine.py` | WIN/LOSS confidence band tuning | **LEGACY** — entry confidence |
| `optimizer.py` | Unrelated portfolio optimizer | **LEGACY** |
| `v41_gate.py` | Action gate adjusted thresholds | **LEGACY** — not profit growth |
| `rebalance_edge_engine.py` | No profit-target logic found | **N/A** |

### Historical / research exit analysis

| Module | What it computes | Classification |
|--------|------------------|----------------|
| `tae_phase7_exit_counterfactual_demo.py` + `research_core/exit_analysis/` | SELL counterfactual analysis | **REPORT_ONLY** — not integrated per-ticker target SSOT |
| `momentum_position_management_v14.py` | Hold-days backtest matrix, stop/reentry simulation | **LEGACY** — research backtest, not live profit targets |
| `missed_winners_audit.py` | Missed winner audit CSV | **LEGACY** — superseded by GA + ledger |
| `TAE_PERFORMANCE1_PROFIT_GROWTH_ARCHITECTURE.md` | Design doc for PROTECT-2 counterfactuals | **REPORT_ONLY** — architecture reference |

---

## Classification summary

| Bucket | Items |
|--------|-------|
| **EXISTS_CAN_REUSE** | GII, GA, ledger, lifecycle JSON; shadow static rules + estimates; validation best strategy; PIB/PDG/PPG/APPE; memory/context |
| **EXISTS_NEEDS_EXTENSION** | Opportunity ledger (`TEST_PARTIAL_TP_AT_DYNAMIC_THRESHOLD` is a label only — needs numeric adapter); GII `recommended_shadow_strategy` (needs target % mapping) |
| **PARTIAL_OVERLAP** | Lifecycle `optimal_shadow_action`; fade/trailing shadow sim; exit counterfactual demos; core exit_intelligence |
| **REPORT_ONLY** | PERFORMANCE-1 architecture, PROTECT rules reports, exit counterfactual outputs |
| **LEGACY** | threshold_*, confidence_optimizer, missed_winners_audit, momentum_position_management_v14 |
| **MISSING** | Unified per-ticker **dynamic** profit target SSOT: partial TP %, trailing distance %, hold ceiling %, exit window urgency, profit target USD — adapted from lifecycle + GII scores |

---

## Coverage estimate vs DPTI intent

| DPTI capability | Existing coverage | Gap |
|-----------------|-------------------|-----|
| Static take-profit thresholds | ✅ Shadow rules v1 (6/8/10%) | Dynamic adjustment per ticker |
| Trailing targets | ✅ Shadow 1% / 1.5% + live core 4%/5% | Per-ticker dynamic trailing from GII |
| Partial take-profit sizing | ✅ Shadow 20%/30% test sells | Dynamic partial % from opportunity/lifecycle |
| Exit window / urgency | ⚠️ PSP urgency, PCE verdict | Numeric exit window / time-to-protect |
| Growth optimization scores | ✅ GII growth_score, future_growth_potential | Map scores → target levels |
| Capture rate / missed analytics | ✅ GA + ledger | Already complete — reuse only |
| Hold optimization targets | ❌ | Suggested hold ceiling / min capture % |
| Portfolio target policy | ⚠️ APPE `TIGHTEN_TRAILING_SHADOW` | Portfolio-level target bias only |

**Weighted coverage: ~68%** → triggers decision rule **EXTEND EXISTING PROFIT / GROWTH STACK**, not standalone engine.

---

## What can be reused (read-only)

| Source | Reuse for DPTI |
|--------|----------------|
| `tae_growth_intelligence.json` | Primary input: growth_score, winner_quality, opportunity_score, lifecycle fields, recommended_shadow_strategy |
| `tae_winner_lifecycle_profiler.json` | lifecycle_stage, collapse/survival, decay velocity |
| `tae_opportunity_cost_ledger.json` | opportunity_category, severity, recommended_shadow_fix |
| `tae_profit_growth_analytics.json` | capture rate, missed_usd, growth_status |
| `tae_profit_protection_shadow.json` | Static baseline thresholds (`rules_v1_config.partial_levels`), per-ticker estimates |
| `tae_profit_protection_validation.json` | Portfolio best shadow method validation |
| `tae_profit_decision_governor.json` | Governor recommendation alignment |
| `tae_adaptive_profit_policy_engine.json` | Policy bias (e.g. tighten trailing) |
| `tae_accounting_snapshot.json` | Corrected PnL context |

---

## What should be extended (not rebuilt)

1. **GII layer** — add optional downstream consumer only; do not fold target math into GII (keeps separation of concerns).  
2. **Opportunity ledger fix labels** — map `TEST_PARTIAL_TP_AT_DYNAMIC_THRESHOLD` to computed `%` values in new adapter output.  
3. **Shadow rules v1** — treat as **baseline anchor**; DPTI adjusts ± from baseline using GII/lifecycle deltas.

---

## What must NOT be rebuilt

| Module / area | Reason |
|---------------|--------|
| `tae_profit_protection_shadow.py` | Already simulates partial/trailing counterfactuals on fade history |
| `tae_profit_protection_validation.py` | Already selects best shadow strategy with gates |
| `tae_profit_intelligence_brain.py` | PSP model is protection-domain SSOT |
| `tae_growth_intelligence.py` scoring | GII is integration SSOT — don't duplicate composite scores |
| `tae_profit_growth_analytics.py` | Capture formulas owned there |
| `tae_opportunity_cost_ledger.py` | Cause taxonomy owned there |
| `tae_winner_lifecycle_profiler.py` | Lifecycle heuristics owned there |
| `core/trailing.py`, `live_bot.py` | Live execution — forbidden |
| `threshold_*` stack | Entry-score domain, not profit-target domain |
| Fade history replay math | Owned by intraday fade + shadow engines |

---

## True missing capability

A **read-only Dynamic Profit Target Intelligence adapter** that:

- Consumes GII + lifecycle + shadow baseline + validation bias  
- Outputs per ticker:
  - `dynamic_partial_tp_pct` (adjusted from 6/8/10% baseline)
  - `dynamic_trailing_pct` (adjusted from 1%/1.5% or policy tighten)
  - `dynamic_profit_lock_pct` (adjusted from 4% baseline)
  - `hold_ceiling_pct` / `min_capture_pct`
  - `exit_window_urgency` (LOW/MEDIUM/HIGH/CRITICAL)
  - `suggested_partial_size_pct` (20/25/30/33/50 shadow sizing)
  - `confidence`, `explanation`
- Outputs portfolio:
  - `portfolio_target_policy`, `dominant_target_mode`, `global_verdict`
- **Does not** execute, advise live bot, or rewrite shadow simulation

This is **~32% net new** — the mapping/adaptation layer only.

---

## Recommended implementation strategy

| Action | Scope |
|--------|-------|
| **REUSE** | All JSON SSOT listed above; shadow `rules_v1_config` as baseline |
| **EXTEND** | Profit Growth CLI chain optionally: `growth-intelligence` → new `profit-targets` command that reads only JSON |
| **BUILD SMALL ADAPTER** | New file e.g. `tae_dynamic_profit_target_intelligence.py` (~300–450 lines, stdlib only) |
| **DO NOT BUILD** | New shadow simulator, new PSP model, new lifecycle classifier, new capture-rate engine, live trailing changes |

---

## Proposed DPTI scope (if approved)

**Name:** Dynamic Profit Target Intelligence (DPTI) — SHADOW_ONLY adapter  
**Checkpoint after:** X.PROFIT-GROWTH-5  

### Inputs (read-only)

Required: `tae_growth_intelligence.json`, `tae_winner_lifecycle_profiler.json`, `tae_opportunity_cost_ledger.json`, `tae_profit_protection_shadow.json`  
Optional: `tae_profit_protection_validation.json`, `tae_profit_growth_analytics.json`, `tae_adaptive_profit_policy_engine.json`

### Adaptation heuristic (example — not implemented yet)

| Condition | Target adjustment |
|-----------|-------------------|
| lifecycle COLLAPSED / PROFIT_DECAY + high opportunity | Lower partial TP threshold (−1–2%), tighten trailing (−0.25%), urgency CRITICAL |
| KEEP_GROWING_SHADOW + high survival | Raise hold ceiling, defer partial TP (+1%), wider trailing |
| ledger NO_PARTIAL_TAKE_PROFIT | Suggest earlier partial TP (−1% from baseline 6%) |
| APPE TIGHTEN_TRAILING_SHADOW | Portfolio bias: trailing distance −0.25% |
| validation best = shadow_trailing_1 | Anchor trailing at 1% unless lifecycle weakens |

### Outputs

`tae_dynamic_profit_target_intelligence.json`, `.md`, sprint report, optional CLI `python3 tae.py profit-targets`

---

## Files future DPTI should read

```text
tae_growth_intelligence.json          ← primary
tae_winner_lifecycle_profiler.json
tae_opportunity_cost_ledger.json
tae_profit_protection_shadow.json     ← static baseline
tae_profit_growth_analytics.json
tae_profit_protection_validation.json
tae_adaptive_profit_policy_engine.json
tae_profit_decision_governor.json
tae_accounting_snapshot.json
```

Optional context: `tae_profit_memory_engine.json`, `tae_profit_context_engine.json`

---

## Files future DPTI must NOT touch

```text
live_bot.py
core/                          (trailing.py, exit_intelligence.py, trades.py)
portfolio.csv
live_signals.csv
watchlist.txt
tae_profit_protection_shadow.py    ← read JSON output only; do not modify engine
tae_profit_intelligence_brain.py
threshold_* / intelligence/threshold_*
momentum_position_management_v14.py
research_core/exit_analysis/       ← separate research lane
```

---

## Duplicate audit result

| Question | Answer |
|----------|--------|
| Do modules already calculate profit targets? | **Yes — static** (shadow 6/8/10%, trailing 1/1.5%, lock 4%) |
| Do modules optimize targets dynamically per ticker? | **No** |
| Do modules integrate growth scores → numeric targets? | **No** |
| Is there an existing integrator for targets? | **No** — GII integrates analytics, not target levels |
| Closest false positive? | `threshold_*` (BUY entry), `confidence_optimizer` (entry confidence), `optimizer.py` |

### Reuse decision

**Extend stack + small adapter.** Reuse 68% of building blocks; build only the missing dynamic target mapping layer.

### Why this does not duplicate existing logic

DPTI would **not** recompute missed USD, lifecycle stages, opportunity categories, shadow PnL simulations, or GII composite scores. It would **translate** those outputs into per-ticker numeric profit targets using shadow rules v1 as baseline — a capability no current module exposes as SSOT.

---

## Confirmation

| Rule | Status |
|------|--------|
| READ_ONLY | ✅ Audit only — no engine created |
| NO_BROKER | ✅ |
| NO_EXECUTION | ✅ |
| NO_PORTFOLIO_CHANGE | ✅ |
| NO_LIVE_BOT_CHANGE | ✅ |
| NO_ADVISORY_CHANGE | ✅ |
| NO_COMMIT | ✅ |

---

## Overall pre-build verdict

**PROCEED with X.PROFIT-GROWTH-5 as EXTEND + SMALL ADAPTER** — not a new independent engine.

**PASS** (audit complete, duplication risk controlled).
