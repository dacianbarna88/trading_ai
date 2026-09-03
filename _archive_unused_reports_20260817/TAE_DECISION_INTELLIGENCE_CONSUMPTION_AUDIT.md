# TAE Decision Intelligence Consumption Audit

**Generated:** 2026-07-08T20:45:00+00:00  
**Branch:** `cursor/x12b-legacy-archive-hotfix`  
**HEAD:** `09c13bb` — Canonical architecture committed  
**Mode:** READ ONLY — no code changes, no commits  
**Final authority audited:** `tae_paper_decision_engine.py` (PDE) — `build_decision()` / `score_actions_for_ticker()`

---

## Executive verdict

### **PARTIALLY_CONNECTED**

The Main Decision Brain **does consume** the primary PAPER intelligence stack end-to-end: hard risk → profit/growth stack (GII/PPG/APPE/shadow) → learning artifacts → conflict-resolution EV evidence → decision-state switch gate → explicit action output.

However, **material intelligence is produced but not scored**, and several **feedback paths lag by one full-paper-cycle** because they run **after** PDE in the same cycle (outcome memory, rule survival, adaptive weights, DPE chain).

| Metric | Estimate |
| --- | ---: |
| Ecosystem intelligence **materially consumed** by final PDE decision | **~65%** |
| Ecosystem intelligence **unused, indirect-only, or next-cycle lag** | **~35%** |
| Readiness for profit validation | **READY** (core path closed; gaps are wiring optimization, not missing brain) |

---

## PDE decision path (backward trace)

```
live_signals.csv + portfolio.csv + paper_portfolio.json
        ↓
build_context()  ← 20+ JSON/CSV artifacts
        ↓
score_actions_for_ticker()
  [1] enforce_hard_risk_discipline()          → may force SELL_PAPER (override)
  [2] GII / PPG / APPE / shadow core scoring
  [3] apply_horizon_action_bias()
  [4] apply_stale_source_penalty()            ← historical runtime
  [5] apply_knowledge_base_bias()
  [6] apply_named_confidence_rules()          ← confidence + replay (minimal)
  [7] apply_longitudinal_knowledge_bias()
  [8] apply_dpe_evaluator_bias()
  [9] apply_learning_evidence_bias()
 [10] apply_adaptive_paper_weights()
 [11] protection_validation_bias()
 [12] experiment_boost + apply_rule_lifecycle_bias()
 [13] apply_conflict_resolution_bias()        ← conflicts.json
 [14] apply_decision_state_gate()             ← active_decisions.json
 [15] apply_hypothesis_rules()                 ← may force SKIP_PAPER
        ↓
build_decision() → paper_decisions.json (FINAL per ticker)
        ↓
paper-execution (downstream — not input to PDE)
```

**Orchestration:** `tae_structural_governance.py` runs decision-state-refresh and conflict-resolution-refresh **before** `paper-decisions`; outcome-memory, rule-survival, adaptive-weights, and DPE **after** PDE.

---

## Matrix 1 — Subsystem consumption

| Subsystem | Produces intelligence | Consumed | Influences PDE | Evidence |
| --- | --- | --- | --- | --- |
| **Hard Risk** | YES | YES | YES | `hard_risk_guardian.py` → `runtime_outputs/governance/hard_risk.json` → `enforce_hard_risk_discipline()` |
| **Decision State** | YES | YES | YES | `tae_decision_state.py` → `active_decisions.json` → `apply_decision_state_gate()` |
| **Conflict Resolution** | YES | YES | YES | `tae_conflict_resolution.py` → `conflicts.json` → `apply_conflict_resolution_bias()` |
| **Investment Council** | YES | NO (by PDE) | NO | `tae_investment_council.py` — runs step 19, synthesis report only |
| **Adaptive Weights** | YES | YES (lag-1) | YES | `paper_action_weights.json` → `apply_adaptive_paper_weights()` |
| **Rule Survival** | YES | YES (lag-1) | YES | `rule_lifecycle.json` → `apply_rule_lifecycle_bias()` |
| **Knowledge Consumption (KB)** | YES | YES | YES | `tae_knowledge_base.json` → `apply_knowledge_base_bias()` |
| **Longitudinal Memory** | YES | PARTIAL | PARTIAL | `knowledge.json` → PDE; `adaptation_hints.json` → confidence nudge only in `build_decision()` |
| **Outcome Memory** | YES | INDIRECT | INDIRECT | Feeds next-cycle weights/hints/knowledge; runs after PDE |
| **Historical Refresh** | YES | YES | YES | `load_horizon_ssot()` + `apply_stale_source_penalty()` + hist confidence in `build_decision()` |
| **Profit Context** | YES | INDIRECT | INDIRECT | `tae_profit_context_engine.json` → GII/PPG/APPE → PDE (no direct PDE read) |
| **Confidence Evolution** | YES | YES | YES | `apply_named_confidence_rules()` + `apply_learning_evidence_bias()` |
| **Decision Governor** | YES | NO | NO | Legacy advisory; `LEGACY_SHADOW` in governance map |
| **DPE** | YES | PARTIAL | PARTIAL | PDE reads `evaluation.json` + `adaptive.json` only; not raw competitive/collaborative portfolios |
| **Market Philosophy** | YES | INDIRECT | PARTIAL | Lab → DPE chain → `preferred_philosophy`; lab JSON not read by PDE |
| **Counterfactual Analysis** | YES | NO | NO | `research_core/entry_analysis`, `exit_analysis` — not in PDE or CR path |
| **Paper Execution** | YES | NO (input) | NO | Downstream consumer of PDE output |
| **Paper Accounting** | YES | PARTIAL | PARTIAL | `tae_accounting_snapshot.json` → `cash_hint` only in PDE |
| **Promotion Lock** | YES | NO (PDE) | NO | Governance gate step 18; blocks live promotion, not PDE scores |

**Additional fully connected (not in minimum list):** GII, PPG, APPE, profit protection shadow/validation, LTP hypotheses/experiments, live signals — dominant core scorers in `score_actions_for_ticker()`.

---

## Matrix 2 — Information flow

| Information | Producer | Consumer | Final decision impact |
| --- | --- | --- | --- |
| Stop-loss / critical loss breach | `hard_risk_guardian.py` | PDE `enforce_hard_risk_discipline()` | **HIGH** — can force SELL_PAPER |
| Active decision + switch auth | `tae_decision_state.py` | PDE `apply_decision_state_gate()` | **HIGH** — blocks unauthorized BUY↔SELL churn |
| Scenario EV table + winner | `tae_conflict_resolution.py` | PDE `apply_conflict_resolution_bias()` | **HIGH** — ±10–38 score points |
| Growth scores, lifecycle, strategy | `tae_growth_intelligence.py` | PDE core scoring | **HIGH** — primary action selection |
| Portfolio governor posture | `tae_portfolio_profit_governor.py` | PDE core scoring | **HIGH** — SELL/REDUCE/PROTECT |
| APPE policy state | `tae_adaptive_profit_policy_engine.py` | PDE BUY/SKIP bias | **MEDIUM** |
| Protection shadow signals | `tae_profit_protection_shadow.py` | PDE core scoring | **MEDIUM–HIGH** |
| Protection validation gates | `tae_profit_protection_validation.py` | PDE `protection_validation_bias()` | **MEDIUM** |
| Paper action weight multipliers | `tae_adaptive_paper_weights.py` | PDE `apply_adaptive_paper_weights()` | **MEDIUM** (lag-1 cycle) |
| Rule lifecycle states | `tae_rule_survival.py` | PDE `apply_rule_lifecycle_bias()` | **MEDIUM** (lag-1 cycle) |
| KB named rules | `tae_knowledge_base.py` | PDE `apply_knowledge_base_bias()` | **MEDIUM** |
| Longitudinal knowledge rules | `tae_longitudinal_outcome_memory.py` | PDE `apply_longitudinal_knowledge_bias()` | **LOW–MEDIUM** (lag-1) |
| DPE evaluator winner | `tae_dpe_result_evaluator.py` | PDE `apply_dpe_evaluator_bias()` | **LOW–MEDIUM** (lag-1) |
| DPE adaptive philosophy | `tae_dpe_adaptive_selector.py` | PDE `preferred_philosophy` bias | **LOW** (lag-1) |
| Confidence hypotheses | `tae_confidence_evolution.py` | PDE named rules | **LOW–MEDIUM** |
| Decision replay readiness | `tae_decision_replay_composer.py` | CR `probability_success()` → conflicts.json → PDE | **LOW** (indirect) |
| Adaptation hints | `tae_longitudinal_outcome_memory.py` | PDE `build_decision()` confidence only | **LOW** (not score) |
| Pattern discovery summary | `pattern_discovery_engine.py` | PDE +3 ROTATE if file exists | **LOW** |
| Accounting cash | `tae_accounting_snapshot.py` | PDE `cash_hint` | **LOW** |
| Horizon / historical SSOT | `tae_historical_runtime_refresh.py` + CSVs | PDE horizon + stale penalty | **MEDIUM** |
| LTP hypotheses + experiment verdicts | LTP + experiment runner | PDE boost + `apply_hypothesis_rules()` | **MEDIUM** — REJECT → SKIP |
| Investment council brief | `tae_investment_council.py` | None in PDE path | **NONE** |
| Counterfactual entry/exit | `research_core/*` | None | **NONE** |
| DPE portfolio metrics (raw) | DPE executors | None in PDE | **NONE** (aggregate only via eval) |
| Market philosophy lab scores | `tae_market_philosophy_lab.py` | DPE events only | **NONE direct** |
| Promotion lock verdict | `tae_live_promotion_lock.py` | Governance only | **NONE on PDE** |

---

## Matrix 3 — Connection status

| Subsystem | Status | Notes |
| --- | --- | --- |
| Hard Risk | **CONNECTED** | First gate; override before soft logic |
| Decision State | **CONNECTED** | Switch authorization wired post-59982ee |
| Conflict Resolution | **CONNECTED** | Pre-PDE refresh; EV bias in scoring |
| GII / PPG / APPE / Shadow stack | **CONNECTED** | Dominant scorers |
| Adaptive Weights | **PARTIALLY_CONNECTED** | Fully wired but **lag-1 cycle** |
| Rule Survival | **PARTIALLY_CONNECTED** | Lifecycle bias wired; **lag-1 cycle** |
| Knowledge Base | **CONNECTED** | Named rule deltas applied |
| Longitudinal Memory | **PARTIALLY_CONNECTED** | `knowledge.json` scored; hints confidence-only |
| Outcome Memory | **PARTIALLY_CONNECTED** | Produces next-cycle inputs |
| Historical Refresh | **CONNECTED** | Horizon + stale penalties |
| Profit Context Engine | **PARTIALLY_CONNECTED** | Indirect via GII/PPG only |
| Confidence Evolution | **CONNECTED** | Named rules + DO_NOT_PROMOTE |
| Decision Governor | **NOT_CONNECTED** | Legacy live advisory |
| DPE (full stack) | **PARTIALLY_CONNECTED** | Eval + adaptive summary only |
| Market Philosophy Lab | **PARTIALLY_CONNECTED** | Indirect via DPE adaptive |
| Counterfactual Analysis | **NOT_CONNECTED** | research_core isolated |
| Paper Execution | **NOT_CONNECTED** (input) | Downstream only |
| Paper Accounting | **PARTIALLY_CONNECTED** | Cash hint only |
| Promotion Lock | **NOT_CONNECTED** (PDE) | Live gate only |
| Investment Council | **NOT_CONNECTED** | Synthesis report after cycle |

---

## Per-subsystem detail (minimum set)

### Hard Risk
1. Produces: YES — position breach status, required action  
2. Information: STOP_LOSS_BREACHED, CRITICAL_LOSS, pnl_pct  
3. Storage: `runtime_outputs/governance/hard_risk.json`  
4. Consumer: PDE directly  
5. PDE direct: **YES**  
6. —  
7. Influences PDE: **YES**  
8. Can change decision: **YES** — forces SELL_PAPER  
9. Evidence: `hard_risk_guardian.py:write_paper_hard_risk_report` → `tae_paper_decision_engine.py:enforce_hard_risk_discipline` (L199–237)

### Decision State
1. YES — last executed action, cooldown, churn, EV margin  
2. Active decision registry per ticker  
3. `runtime_outputs/decision_state/active_decisions.json`  
4. PDE via `apply_decision_state_gate`  
5. **YES**  
7. **YES**  
8. **YES** — blocks unauthorized switches → HOLD  
9. `tae_decision_state.py:build_active_decisions` → `apply_decision_state_gate` (L492) ← called from `score_actions_for_ticker` (L1554)

### Conflict Resolution
1. YES — scenario EV table, winning scenario, switch flags  
2. EV-ranked BUY/HOLD/SELL scenarios per ticker  
3. `runtime_outputs/conflict_resolution/conflicts.json`  
4. PDE `apply_conflict_resolution_bias`  
5. **YES** (reads precomputed JSON; CR built by `conflict-resolution-refresh`)  
7. **YES**  
8. **YES** — can boost BUY or winner action ±38 points  
9. `tae_conflict_resolution.py:build_conflict_payload` → `apply_conflict_resolution_bias` (L735) ← uses `build_context()` from PDE (L529)

### Investment Council
1. YES — operator synthesis brief  
2. Confidence-ranked findings from existing artifacts  
3. `runtime_outputs/investment_council/council.json`  
4. None in PDE path  
5. **NO**  
6. Human operator only  
7. **NO**  
8. **NO**  
9. `tae_investment_council.py` — step 19 in `tae_structural_governance.py`; no import in PDE

### Adaptive Weights
1. YES — per-action multipliers by ticker  
2. Validation-driven weight adjustments  
3. `runtime_outputs/adaptive_weights/paper_action_weights.json`  
4. PDE `apply_adaptive_paper_weights`  
5. **YES**  
7. **YES** (next cycle after weights step)  
8. **YES** — multiplicative score change  
9. `tae_adaptive_paper_weights.py` → PDE L940–966; cycle rank 15 **after** PDE

### Rule Survival
1. YES — rule state TESTING/TRUSTED/DISABLED  
2. Influence multipliers per named rule  
3. `runtime_outputs/paper_execution/rule_lifecycle.json`  
4. PDE `apply_rule_lifecycle_bias`  
5. **YES**  
7. **YES** (lag-1)  
8. **YES** — DISABLED blocks positive rule deltas  
9. `tae_rule_survival.py` → PDE L152–196; rank 14 after PDE

### Knowledge Consumption
1. YES — consolidated KB entries with pattern/recommendation  
2. Named shadow rules (SCORE_DECAY, TRAILING, etc.)  
3. `tae_knowledge_base.json`  
4. PDE `apply_knowledge_base_bias`  
5. **YES**  
7. **YES**  
8. **YES** when entries match NAMED_RULE_SCORE_DELTAS  
9. PDE L768–812

### Longitudinal Memory / Outcome Memory
1. YES — memory records, adaptation hints, knowledge rules  
2. Action confidence bias; rule_id confidence deltas  
3. `runtime_outputs/longitudinal_memory/*`  
4. PDE reads `knowledge.json` + `adaptation_hints.json`  
5. **PARTIAL** — hints not in score path  
7. **PARTIAL**  
8. **UNKNOWN** for hints alone; **YES** for knowledge rules  
9. `apply_longitudinal_knowledge_bias` L849; hints L1616–1620 in `build_decision`

### Historical Refresh
1. YES — stale source detection, confidence penalty  
2. Horizon returns, cross-validation, runtime state  
3. `runtime_outputs/historical_runtime/runtime_state.json` + root CSVs/TXTs  
4. PDE `load_horizon_ssot`, `apply_stale_source_penalty`, `build_horizon_context`  
5. **YES**  
7. **YES**  
8. **YES** — can block BUY via horizon gate  
9. PDE L508–573, L694–710, L969–1018; `tae_historical_runtime_refresh.py`

### Profit Context
1. YES — risk/context enrichment  
2. Context alignment, regime hints  
3. `tae_profit_context_engine.json`  
4. GII, PPG, APPE, shadow producers — not PDE  
5. **NO**  
6. `tae_growth_intelligence.py`, `tae_portfolio_profit_governor.py`  
7. **YES** (indirect via GII/PPG)  
8. **UNKNOWN** direct; **YES** indirect  
9. No `profit_context` string in `tae_paper_decision_engine.py`

### Confidence Evolution
1. YES — hypothesis entries, final recommendation  
2. SCORE_DECAY_SHADOW, DO_NOT_PROMOTE aggregates  
3. `tae_confidence_evolution.json`  
4. PDE direct  
5. **YES**  
7. **YES**  
8. **YES** — BUY↓ SKIP↑ via named rules  
9. PDE L815–846, L923–933

### Decision Governor
1. YES — live advisory materialization  
2. Advisory recommendations  
3. `tae_decision_governor.json` / `.md`  
4. None in PAPER cycle  
5. **NO**  
7. **NO**  
8. **NO**  
9. `tae_structural_governance.py` marks `LEGACY_SHADOW`

### DPE
1. YES — dual-arm paper metrics, evaluation, learning, adaptive preference  
2. Winner philosophy, confidence_pct, per-arm metrics  
3. `runtime_outputs/dpe/**`  
4. PDE reads eval + adaptive only  
5. **PARTIAL**  
6. Summary via `apply_dpe_evaluator_bias`, philosophy via `preferred_philosophy`  
7. **PARTIAL**  
8. **YES** for winner/adaptive bias; **NO** for raw portfolio diffs  
9. PDE L879–920, L1495–1500; DPE chain rank 16 **after** PDE

### Market Philosophy
1. YES — competitive vs collaborative model scores  
2. Philosophy fit scores per ticker  
3. `tae_market_philosophy_lab.json` (via DPE events path)  
4. DPE adaptive selector → PDE  
5. **NO** direct  
6. `tae_dpe_adaptive_selector.py`  
7. **PARTIAL**  
8. **YES** small ±3–5 action bias  
9. No import of `tae_market_philosophy_lab` in PDE

### Counterfactual Analysis
1. YES — entry/exit CF scenarios  
2. Alternative path PnL, scenario rankings  
3. `research_core/` JSON outputs  
4. None in PDE/CR  
5. **NO**  
7. **NO**  
8. **NO**  
9. No references in `tae_paper_decision_engine.py` or `tae_conflict_resolution.py`

### Paper Execution
1. YES — fills, portfolio state  
2. Positions, orders, trades  
3. `runtime_outputs/paper_execution/*`  
4. PDE reads **portfolio positions only** (not orders as decision input)  
5. **PARTIAL** — positions yes, execution logic no  
7. **PARTIAL** — position held affects scoring branch  
8. **YES** via held vs not-held branches  
9. `PAPER_PORTFOLIO_JSON` in `build_context` L1075–1076

### Paper Accounting
1. YES — canonical accounting snapshot  
2. cash_available, account_value  
3. `tae_accounting_snapshot.json`  
4. PDE `cash_hint` only  
5. **PARTIAL**  
7. **PARTIAL**  
8. **YES** when cash < $1000 → SKIP/BUY bias  
9. PDE L1070, L1487–1490

### Promotion Lock
1. YES — live promotion gate  
2. live_promotion_allowed, checklist  
3. `runtime_outputs/full_paper_cycle/promotion_gate.json`  
4. Governance / operator — not PDE  
5. **NO**  
7. **NO**  
8. **NO** on PAPER action  
9. `tae_live_promotion_lock.py` step 18; no PDE import

---

## Unused intelligence — what exists vs what is not consumed

| Already exists | Not consumed by PDE | Minimal wiring (no new modules) | Decision quality impact |
| --- | --- | --- | --- |
| `research_core` counterfactual entry/exit JSON | Full scenario rankings | Feed top CF delta into CR `probability_success()` or PDE horizon bias | **Medium** — better drawdown estimates |
| `tae_market_philosophy_lab.json` per-ticker scores | Only aggregate `preferred_philosophy` | Read lab JSON in PDE for ticker-level philosophy fit ±score | **Low–Medium** |
| DPE competitive/collaborative portfolio metrics | Only eval winner string | Pass per-ticker arm PnL delta from eval JSON into CR EV table | **Medium** |
| `adaptation_hints.json` action biases | Confidence nudge only | Apply hint deltas in `score_actions_for_ticker` not just `build_decision` | **Low–Medium** |
| `pattern_discovery_summary.txt` content | File-exists +3 ROTATE | Parse summary keywords → named rule mapping | **Low** |
| `tae_decision_replay.json` full scenarios | readiness + DO_NOT_PROMOTE only | Expand CR opposing_modules using replay scenarios | **Low** |
| Investment council findings | Operator report | Optional: read council.json as PDE evidence (read-only bias) | **Low** (operator-facing) |
| Profit target adapter outputs | None | Map targets into PROTECT/REDUCE thresholds in PDE held branch | **Medium** for profit-taking |
| One-cycle lag (weights, lifecycle, DPE) | Same-cycle PDE miss | Re-order governance: refresh weights/DPE **before** PDE when same-run feedback needed | **High** for learning loop latency |

---

## Top 10 highest-value existing components not fully influencing decisions

| Rank | Component | Why high value | Current gap |
| ---: | --- | --- | --- |
| 1 | **Counterfactual entry/exit** (`research_core`) | Rich alternative-path EV | Not in PDE or CR path |
| 2 | **DPE raw portfolio comparison** | Direct philosophy performance | Only winner summary in PDE |
| 3 | **Profit target adapter** | Dynamic exit targets | Not referenced by PDE |
| 4 | **Adaptation hints (score path)** | Validated action biases | Confidence-only in `build_decision` |
| 5 | **Market philosophy lab per-ticker** | Philosophy fit signal | Indirect via DPE adaptive only |
| 6 | **Decision replay scenarios** | Historical similar decisions | Minimal CR/PDE use |
| 7 | **Pattern discovery content** | Rotation candidates | Boolean file check only |
| 8 | **Profit decision committee/governor** | Shadow committee votes | Legacy stack, not PDE |
| 9 | **Investment council synthesis** | Cross-subsystem ranking | Report-only |
| 10 | **Same-cycle feedback lag** | Weights/lifecycle/DPE | Structural ordering, not missing code |

---

## Readiness for profit validation

**Verdict: READY for disciplined PAPER profit validation**

Rationale:
- Single final authority (PDE) confirmed closed at `b48a3c7`
- Hard risk, decision state, and conflict resolution are **connected** and tested
- Core profit intelligence (GII, PPG, shadow, validation) **directly scores** actions
- Learning feedback operates with **one-cycle lag** — acceptable for validation if cycles run sequentially
- Unused intelligence is **optimization surface**, not a missing decision brain

Recommended validation protocol: run sequential `full-paper-cycle` with pre-populated prior-cycle weights/DPE artifacts; do not expect same-run adaptive feedback until cycle N+1.

---

## Final answer summary

| Question | Answer |
| --- | --- |
| Executive verdict | **PARTIALLY_CONNECTED** |
| Intelligence consumed by final decision | **~65%** |
| Intelligence unused / indirect / lagged | **~35%** |
| Profit validation readiness | **READY** |
| New modules required | **None** — wiring and cycle-order only |

Machine-readable companion: `tae_decision_intelligence_consumption_audit.json`
