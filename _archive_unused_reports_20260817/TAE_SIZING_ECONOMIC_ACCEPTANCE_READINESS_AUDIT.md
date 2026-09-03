# TAE Sizing Economic Acceptance Readiness Audit

**Audit ID:** `TAE_SIZING_ECONOMIC_ACCEPTANCE_READINESS_AUDIT`  
**Date:** 2026-07-28  
**HEAD:** `d263961`  
**Mode:** STRICT READ-ONLY (this file is the only permitted write)  
**Experiment:** `TAE_SHADOW_SIZING_COMPARISON_V1`  
**Scope:** Can TAE decide rigorously whether an alternate sizing formula has economic edge, controlled risk, and robustness — without promoting any formula?

---

## EXECUTIVE_VERDICT

Measurement infrastructure for sizing counterfactuals is **present** (Level 0 shadow + Level 2 observed-path replay + attribution separation). A **sizing-specific economic acceptance / promotion gate SSOT does not exist**.

Current PAPER counterfactual sample contains **only control ledgers** (`EXECUTED_OBSERVED_QTY`). **Zero** journal fills carry `shadow_sizing_evaluations` (all V1/V2 buys predate or lack post-`f12ec20` shadow persistence). Therefore **no challenger formula can be economically accepted or rejected from PAPER CF evidence today**.

Offline risk-weighted sizing remains **`RISK_WEIGHTED_SIZING_NO_EDGE`** with `promotion_eligibility=false` — not a promotion candidate.

Adjacent gates (strategy promotion review, live promotion lock, attribution winner sample floors, chrono reliability flags) are **reusable patterns**, not a connected sizing acceptance pipeline.

**FINAL_VERDICT:** `TAE_SIZING_ACCEPTANCE_NOT_JUSTIFIED_YET`  

**NEXT_SINGLE_SPRINT:** `NO_IMPLEMENTATION_JUSTIFIED_CONTINUE_COLLECTION`

Do **not** BUILD an acceptance gate until PAPER CF ledgers exist for challenger `formula_id`s with sufficient closed cycles and clean reconciliation.

---

## 1. EXISTING_ACCEPTANCE_COMPONENTS

| FILE | FUNCTION/CLASS | OWNER | PURPOSE | INPUTS | OUTPUTS | PERSISTENCE | CALL_SITES | RUNTIME_PATH | TESTS | STATUS | REUSABILITY (sizing) | DUPLICATION_RISK |
|------|----------------|-------|---------|--------|---------|-------------|------------|--------------|-------|--------|----------------------|------------------|
| `research_core/strategy_evolution/promotion_gate.py` | `StrategyPromotionGate.evaluate` | Strategy evolution Phase VIII | Review-only: paper candidates vs baseline | ranking/validation/registry JSON | `PromotionGateReport` | `tae_strategy_promotion_gate.json` | pipeline demos | OFFLINE / REPORT | promotion_gate tests/demo | **OFFLINE_ONLY** | Medium — sample/baseline blockers reusable as *pattern* | High if BUILD parallel sizing gate without reuse |
| `research_core/strategy_evolution/promotion_gate_report.py` | `PROMOTION_MIN_TRADES=20`, score 0.70 | Same | Threshold constants for strategy candidates | — | enums/decisions | report files | promotion_gate | REPORT_ONLY | yes | **REPORT_ONLY** | Low for sizing (different object) | Medium |
| `tae_live_promotion_lock.py` | `enforce_promotion_gate`, `run_live_promotion_lock_audit` | Phase 9 lock | Hard-lock `live_promotion_allowed=false` | full-paper promotion_gate.json | lock report | `TAE_LIVE_PROMOTION_LOCK_REPORT.md` | full_paper_cycle, structural governance | CONNECTED (lock) | CLI | **IMPLEMENTED_AND_CONNECTED** | High for LIVE safety; not sizing accept | Low |
| `tae_decision_replay_promotion.py` | `evaluate_promotion` | Decision replay | Advisory promotion audit | decision replay JSON | audit JSON/MD | reports | CLI | REPORT_ONLY | promotion tests | **REPORT_ONLY** | None for sizing qty | Low |
| `tae_profit_target_promotion.py` | PTA promotion audit | Profit target | PTA→PDE eligibility audit | paper outcomes | audit | reports | CLI | REPORT_ONLY | PTA tests | **REPORT_ONLY** | Wrong domain | Medium |
| `tae_roi001_challenger.py` | ROI-001 challenger flags | PAPER challenger | Partial-size challenger vs baseline | PTA rows | flags/report | JSON | paper_execution | PAPER PARTIAL | ROI tests | **PARTIAL** | Pattern: challenger flag | Medium |
| `tae_paper_experiment_runner.py` | `run_experiments` | PAPER research | Hypotheses; always `live_promotion_allowed=false` | paper context | reports | paper outputs | CLI | REPORT_ONLY | experiment tests | **REPORT_ONLY** | Weak registry pattern | Medium |
| `tae_paper_economic_attribution.py` | `MIN_CLOSED_CYCLES_FOR_WINNER=30`, `MIN_OBSERVATION_DAYS_FOR_WINNER=20` | Attribution | Winner declaration sample floor (V1 vs V2) | closed cycles | `sample_sufficient_for_winner` | attribution summary | rebuild | PAPER | attribution tests | **IMPLEMENTED_AND_CONNECTED** | **High** as sample floor reference | Low if EXTEND |
| `tae_chronological_portfolio_replay.py` | `reliable_for_promotion`, `promotion_eligibility=False` | Offline SIZE | Reliability flags for chrono A/B | variant metrics | report | results JSON/MD | risk-weighted AB | OFFLINE | chrono tests | **OFFLINE_ONLY** | Medium | Medium |
| `tae_risk_weighted_sizing_ab.py` | verdict `RISK_WEIGHTED_SIZING_NO_EDGE` | Offline sizing A/B | Economic reject of ATR/conf/DD sizing | portfolio.csv SIZE | verdict | results MD/JSON | CLI | OFFLINE_ONLY | AB tests | **OFFLINE_ONLY** | **High** as prior reject evidence | Low |
| `tae_dpe_validation_start_gate.py` | `run_gate` | DPE start gate | Preflight before DPE validation | paper arms/guards | gate verdict | reports | CLI | REPORT / ops | — | **IMPLEMENTED_NOT_CONNECTED** to sizing CF | Low | Medium |
| `research_core/validation/walk_forward.py` | `WalkForwardValidator` | Research validation | WF splits for hypotheses | cohorts | scores | research | discovery | OFFLINE_ONLY | research | **OFFLINE_ONLY** | Medium later | Medium |
| `tae_paper_sizing_counterfactual_replay.py` | `run_sizing_counterfactual_replay` | PAPER CF L2 | Metrics per formula ledger | journals + shadow | CF summary/ledgers | `runtime_outputs/.../counterfactual/` | attribution rebuild | PAPER OBS | CF tests | **IMPLEMENTED_AND_CONNECTED** | **Required input** to any future gate | High if BUILD new metrics engine |
| `tae_paper_shadow_sizing.py` | `evaluate_shadow_sizing` | L0 observability | Persist alt qty at fill | prefill | evaluations | journals | parallel runtime | PAPER | shadow tests | **IMPLEMENTED_AND_CONNECTED** | Required for challenger sample | Low |
| `tae_confidence_evolution.py` / `tae_decision_governor.py` | DO_NOT_PROMOTE lists | Shadow governor | Soft promote blocks | JSON artifacts | recommendations | generated reports | market-open stack | SHADOW | — | **REPORT_ONLY** | Low | Low |
| `migration/legacy/tae_promotion_queue.py` | queue | LEGACY | Old promotion queue | — | csv/json | root | legacy | LEGACY | — | **LEGACY** | None | — |
| Sizing economic acceptance gate SSOT | — | — | Decide CONTINUE/REJECT/VALIDATE for formula_id | CF metrics | gate decision | — | — | — | — | **ABSENT** | — | — |

---

## 2. COUNTERFACTUAL_SAMPLE_STATUS

### 2.1 Sample strata (do not mix)

| Stratum | Content | Status |
|---------|---------|--------|
| **PAPER_COUNTERFACTUAL_SAMPLE** | `runtime_outputs/parallel_paper/counterfactual/*` after rebuild | **PRESENT but control-only** |
| **CURRENT_SAMPLE** | Same CF rebuild (2026-07-28T13:21:30Z) | Control arms only |
| **HISTORICAL_SAMPLE** | Journals without shadow | **No challenger CF**; status `COUNTERFACTUAL_DATA_NOT_PERSISTED_AT_ENTRY` when evaluated |
| **OFFLINE_SAMPLE** | `tae_risk_weighted_sizing_ab` / chrono SIZE on `portfolio.csv` | **Present**; verdict **NO_EDGE**; separate methodology |

### 2.2 PAPER CF aggregate (measured)

| Field | Value |
|-------|-------|
| experiment_id | `TAE_SHADOW_SIZING_COMPARISON_V1` |
| counterfactual_level | LEVEL_2 |
| sample_start (events) | 2026-07-23 |
| sample_end (events) | 2026-07-28 |
| trading / calendar days with events | **3** (2026-07-23, 27, 28) |
| total_events | 19 |
| closed_cycles | 4 |
| ledger_count | 2 |
| formulas_evaluated (challenger) | **0** |
| formula_keys | `V1::EXECUTED_OBSERVED_QTY`, `V2::EXECUTED_OBSERVED_QTY` |
| V1/V2 trades with shadow_sizing_evaluations | **0 / 0** |
| reconciliation_pass (summary) | **false** (V1 control account-identity residual ≈ −71.4; cash identity OK; gross−cost=net OK) |

### 2.3 Per ledger (PAPER CF)

#### `V1::EXECUTED_OBSERVED_QTY` (control — not a challenger)

| Metric | Value |
|--------|-------|
| accepted / rejected / skipped | 14 / 1 / 0 |
| closed_cycles | 4 |
| open_positions (end) | 10 |
| gross / costs / net PnL | −425.48 / 18.07 / −443.55 |
| turnover | 36145.51 |
| capital_utilization_pct / cash_drag_pct | 76.15 / 23.85 |
| win_rate / expectancy / profit_factor | 0.25 / −108.08 / ~0 |
| maximum_ledger_drawdown | −432.05 |
| R-multiple | **NOT in CF summary** |
| net_pnl_delta_vs_executed | N/A (is control) |
| regimes / regions | **NOT persisted** in CF summary |
| tickers touched (events) | 15 names (ABBV, AIR.PA, ALV.DE, DIA, GE, HD, LLY, MRK, MSFT, NVDA, PG, PM, SAP.DE, SIE.DE, ULVR.L) |
| data_quality | **reconciliation_pass=false** (account identity) |

#### `V2::EXECUTED_OBSERVED_QTY`

| Metric | Value |
|--------|-------|
| accepted / closed | 0 / 0 |
| economics | zeros |
| note | V2 journal has no BUY fills in sample window |

#### Challenger formula_ids (LIVE equal-split, core/risk, offline B1/B2/B3, cross-path V1/V2, confidence)

| Metric | Status |
|--------|--------|
| All PAPER CF metrics | **ABSENT** — no shadow evaluations on fills → no `arm::formula_id` ledgers |

### 2.4 Offline sample (separate)

Risk-weighted A/B: **`RISK_WEIGHTED_SIZING_NO_EDGE`**, `promotion_eligibility=false`. Must not be pooled with PAPER CF for acceptance.

---

## 3. SAMPLE_SUFFICIENCY

### 3.1 Canonical rules that exist (not sizing-specific)

| Rule | Source | Value | Applies to sizing CF? |
|------|--------|-------|------------------------|
| Min closed cycles for winner | attribution | **30** | Reference only; **not** wired as sizing gate |
| Min observation days for winner | attribution | **20** | Reference only |
| Strategy promotion min trades | promotion_gate_report | **20** | Strategy candidates, not formula_id |
| Ranking score threshold | promotion_gate_report | **0.70** | Strategy ranking |
| Chrono / risk-weighted promotion_eligibility | offline reports | **false** unless reliability | Offline research |
| live_promotion_allowed | live promotion lock / PDE | **always false** machine-side | LIVE safety |

### 3.2 Missing as institutional sizing acceptance truth

Minimum effect size, CI/power, sequential testing, early stopping, multiple-comparison correction, regime floors, concentration caps, cost veto thresholds for **sizing formulas** — **ABSENT** as a sizing SSOT.  
**This audit does not invent thresholds.**

### 3.3 Classification vs available floors (illustrative only)

Against attribution’s 30 closed / 20 days (existing floors, not a sizing gate):

| Sample | Closed cycles | Days | Verdict vs those floors |
|--------|---------------|------|-------------------------|
| PAPER CF challengers | 0 | 0 with shadow | **INSUFFICIENT_DATA** |
| PAPER CF V1 control | 4 | 3 | **INSUFFICIENT_DATA** (+ recon fail) |
| Offline NO_EDGE | research window | research | **REJECT** for promotion (prior verdict), not PAPER accept |

---

## 4. ECONOMIC_COMPARISON

Ability to compare challenger vs executed on **same observed path** (LEVEL_2):

| Metric | Status |
|--------|--------|
| net PnL | AVAILABLE in CF ledger schema; **INSUFFICIENT_SAMPLE** for challengers |
| expectancy / profit factor | AVAILABLE when closed_cycles>0; insufficient |
| maximum drawdown (ledger) | AVAILABLE (equity curve); insufficient |
| R-multiple | PARTIAL — entry risk freeze exists; CF summary does not emit R yet → **REQUIRES_EXTENSION** for gate input |
| return on capital utilized / capital efficiency | PARTIAL (utilization + net present; formal ratio **REQUIRES_EXTENSION**) |
| risk-adjusted return | UNAVAILABLE / REQUIRES_EXTENSION |
| turnover / costs / cash drag | AVAILABLE in schema |
| rejection rate | AVAILABLE (accepted/rejected counts) |
| concentration / exposure | PARTIAL (open positions/exposure; no formal HHI) |
| stability across tickers/regimes/time | **INSUFFICIENT_SAMPLE** / regime **NOT_APPLICABLE** (not frozen on fills) |

**Net PnL alone is not an acceptance criterion** (Phase X + prior audits). No connected multi-metric sizing gate exists.

---

## 5. RISK_ACCEPTANCE

| Concern | Existing mechanism | Sizing CF wired? |
|---------|-------------------|------------------|
| Drawdown increase | CF `maximum_ledger_drawdown`; offline reliability | Metric only — **no veto gate** |
| Concentration / tail / loss per trade | Not formalized for sizing | **ABSENT** |
| Cash starvation / capital consumption | utilization, cash_drag, NO_CASH rejects | Observability only |
| Turnover / cost inflation | turnover + costs deltas vs executed | Observability only |
| Single ticker / single regime | Not gated | **ABSENT** |
| Hard risk veto | hard_risk_guardian on **executed** path | Not applied to CF formulas |
| Economic / concentration / cost / robustness / DQ veto | Fragmented offline flags | **No sizing acceptance veto SSOT** |

Data-quality veto **should** apply today to any use of V1 control CF for decisions: `reconciliation_pass=false`.

---

## 6. ROBUSTNESS_READINESS

| Capability | Classification |
|------------|----------------|
| Rolling-window / first-half vs second-half | **EXTEND_EXISTING** (events timestamps exist; not implemented for sizing) |
| Walk-forward / OOS | **AVAILABLE_NOW** in research_core; **NOT** connected to sizing CF |
| Per-ticker | **EXTEND_EXISTING** (ticker on events/cycles) |
| Per-sector / region / regime | **BUILD_REQUIRED** or capture EXTEND (regime/sector rarely frozen at fill) |
| High vs low vol | Needs ATR freeze — often missing → **NOT_JUSTIFIED_YET** |
| Cost / capital / limit sensitivity | **EXTEND_EXISTING** (replay params) |
| Bootstrap / permutation | **NOT_JUSTIFIED_YET** (sample too small) |

---

## 7. EXPERIMENT_REGISTRY

For `TAE_SHADOW_SIZING_COMPARISON_V1`:

| Element | State |
|---------|-------|
| experiment_id constant | **Present** (`tae_paper_shadow_sizing.EXPERIMENT_ID`) |
| owner / hypothesis text | Implicit in implementation docs — **no registry SSOT** |
| control formula | De facto executed path + CF `EXECUTED_OBSERVED_QTY` |
| challenger formulas | Inventoried at L0; **not registered with status** |
| start timestamp / sample window | Only regenerable summary timestamps |
| inclusion/exclusion / DQ / accept/reject/stop criteria | **ABSENT** as registry fields |
| result persistence | CF JSON under runtime_outputs (gitignored) |
| audit trail | Commit/docs + CF honesty gates |

**Registry SSOT:** **ABSENT** (fragmented docs + experiment_id + CF outputs ≠ formal registry).

---

## 8. PROMOTION_SAFETY

Desired path:

`SHADOW → COUNTERFACTUAL → FORMAL VALIDATION → PAPER CHALLENGER → PAPER CANONICAL → LIVE ELIGIBILITY`

| Question | Answer |
|----------|--------|
| Exists promotion workflow for sizing formulas? | **No** end-to-end. Pieces: L0 shadow, L2 CF, LIVE lock |
| Manual or automatic? | LIVE locked automatic-deny; sizing promote path **manual-by-absence** |
| Rollback / canary / dual-run for sizing? | Parallel V1/V2 is dual-run for **strategies**, not sizing formulas |
| Approval record? | Operator culture + docs; no sizing approval ledger |
| Minimum observation window? | Attribution/strategy floors exist; **not applied to sizing CF** |
| Automatic demotion? | **ABSENT** for sizing |
| Can a formula change runtime without approval? | **No** — shadow/CF are observability-only; executed sizing unchanged |

**LIVE promotion for sizing: not recommended and machine-blocked.**

---

## 9. DUPLICATION_ANALYSIS

| Capability | Recommendation |
|------------|----------------|
| Validation start gate (DPE) | **REUSE** as ops pattern; do not overload for sizing |
| Experiment framework | **EXTEND** later into registry — not now |
| Economic attribution | **REUSE** floors + CF consume path |
| Counterfactual summary | **REUSE** as evidence input |
| Strategy promotion gate | **REUSE** blocker *pattern* when building gate later |
| Live promotion lock | **REUSE** / keep hard lock |
| Offline A/B (risk-weighted) | **REUSE** as prior REJECT evidence; do not re-run as PAPER accept |
| Research ranking / challenger reports | **RETIRE** from sizing acceptance path (wrong object) |
| New acceptance engine | **NOT_JUSTIFIED_YET** |

---

## 10. CONNECT_REPAIR_EXTEND_BUILD_MATRIX

| Area | Decision |
|------|----------|
| **A. Experiment registry** | **NOT_JUSTIFIED_YET** (collect first; EXTEND later) |
| **B. Sample sufficiency logic** | **NOT_JUSTIFIED_YET** (reuse attribution floors informally; no new SSOT until sample exists) |
| **C. Economic metrics gate** | **NOT_JUSTIFIED_YET** |
| **D. Risk veto gate** | **NOT_JUSTIFIED_YET** |
| **E. Robustness validation** | **NOT_JUSTIFIED_YET** |
| **F. Statistical evaluation** | **NOT_JUSTIFIED_YET** |
| **G. Promotion workflow** | **NO_ACTION_REQUIRED** short-term (LIVE locked; no sizing promote) |
| **H. Rollback/demotion** | **NO_ACTION_REQUIRED** (nothing promoted) |

Optional future (not this sprint): **REPAIR** CF account-identity reconciliation for FX/regional marks before treating control CF as decision evidence; **CONTINUE** shadow capture on new fills.

---

## 11. FORMULA_STATUS_MATRIX

| FORMULA_ID | SAMPLE_STATUS | ECONOMIC_STATUS | RISK_STATUS | ROBUSTNESS_STATUS | DATA_QUALITY_STATUS | CURRENT_DECISION |
|------------|---------------|-----------------|-------------|-------------------|---------------------|------------------|
| EXECUTED_OBSERVED_QTY (control) | CURRENT_SAMPLE control only | Observability metrics only | Drawdown observed; no veto | Insufficient window | **recon fail** on V1 | **PAUSE_FOR_DATA_QUALITY** (as decision evidence) / CONTINUE as control rebuild |
| PAPER_V1_DEPLOYABLE… (executed V1) | No CF challenger ledger | — | — | — | No shadow on fills | **INSUFFICIENT_DATA** → **CONTINUE_OBSERVATION** |
| PAPER_V2_INITIAL/ADD/REENTRY | Same | — | — | — | Same | **CONTINUE_OBSERVATION** |
| LIVE_EQUAL_SPLIT… | No PAPER CF | — | — | — | Same | **CONTINUE_OBSERVATION** |
| CANONICAL_PAPER_CONFIDENCE_PCT | No PAPER CF | — | — | — | Often PARTIAL confidence | **CONTINUE_OBSERVATION** |
| CORE_RISK_GET_DYNAMIC_TRADE_SIZE | No PAPER CF; not connected to exec | — | — | — | NA on ADD | **CONTINUE_OBSERVATION** |
| OFFLINE_RISK_WEIGHTED_B1/B2/B3 | OFFLINE_SAMPLE NO_EDGE | Offline reject | Offline flags | Offline only | Offline | **REJECT** for promotion; PAPER still **CONTINUE_OBSERVATION** until PAPER CF exists |
| Cross-path ACTIVE_SHADOW / NOT_APPLICABLE | L0 inventory only | — | — | — | Path NA explicit | **CONTINUE_OBSERVATION** / skip NA |

No formula is `ELIGIBLE_FOR_FORMAL_VALIDATION` or `ELIGIBLE_FOR_PAPER_CHALLENGER`.

---

## 12. NEXT_SINGLE_SPRINT

**`NO_IMPLEMENTATION_JUSTIFIED_CONTINUE_COLLECTION`**

Reasons:

1. Challenger PAPER CF sample size = **0** (no shadow on fills).
2. Existing closed-cycle floor references (30 / 20 days) are far above current control sample (4 / 3).
3. Measurement stack (L0 + L2 + attribution) is already enough to **collect**.
4. Building an acceptance gate now would encode empty decisions and duplicate strategy/offline gates.
5. Prior offline sizing already **NO_EDGE** — no urgency to promote.

Operator action until next justified sprint: ensure new PAPER fills persist shadow evaluations; rebuild CF; wait for recon-clean ledgers and adequate closed cycles **before** any `EXTEND_EXISTING_EXPERIMENT_VALIDATION` / gate work.

---

## Appendix — Evidence anchors

- CF summary: `runtime_outputs/parallel_paper/counterfactual/counterfactual_summary.json` (`ledger_count=2`, challenger formulas absent).
- Journals: `v1` 15 BUY / 0 with shadow; `v2` 0 BUY in CF window.
- Attribution floors: `MIN_CLOSED_CYCLES_FOR_WINNER=30`, `MIN_OBSERVATION_DAYS_FOR_WINNER=20`.
- Strategy gate: `PROMOTION_MIN_TRADES=20`, score `0.70`.
- Offline: `RISK_WEIGHTED_SIZING_NO_EDGE` / `promotion_eligibility=false`.
- LIVE: `tae_live_promotion_lock.enforce_promotion_gate` → `live_promotion_allowed=false`.

---

**Audit complete. No code, tests, gitignore, or other docs modified. No commit.**
