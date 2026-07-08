# TAE Knowledge / Learning / Adaptive Consumption Audit

**Generated:** 2026-07-07T15:45:00+00:00  
**Mode:** READ_ONLY — NO_BROKER — NO_LIVE_EXECUTION — NO_LIVE_PROMOTION  
**Machine JSON:** `tae_knowledge_consumption_audit.json`

---

## 1. Executive Verdict

### **KNOWLEDGE_CONSUMPTION_GAPS_FOUND**

The PAPER decision loop **does consume** the primary feedback path:

`paper_decisions → validation → longitudinal memory → adaptation_hints + adaptive weights → PDE scoring`

However, several **consolidated knowledge layers** produce rich learning that **does not yet change PAPER scores**. Named confidence hypotheses (`SCORE_DECAY_SHADOW`, `STOP_REENTRY_CHURN`, etc.) are materialized into experiment queues but **not directly wired** into decision scoring.

| Layer | Status |
|---|---|
| Core PAPER feedback (GII, validation, weights) | **Operational** |
| Longitudinal hints + adaptive weights | **Fully consumed by PDE** |
| Knowledge base + knowledge.json rules | **Produced, not consumed by PDE** |
| Named confidence rule materialization | **Partial / indirect only** |
| Strategy evolution / meta outcome learning | **Report-only / legacy** |

**Validation run (this audit):**
- `full-paper-cycle`: **READY_WITH_WARNINGS**
- `adaptive-weights`, `outcome-memory`: **PASS**
- All 25 decisions include `adaptive_weight_evidence`
- Forbidden files git diff: **0 lines**
- Health: **NOT_READY** (live_bot not detected — environmental)

---

## 2. Consumption Matrix

| ID | Artifact | Producer | Integration | Consumed by PAPER path | Decision impact |
|---|---|---|---|---|---|
| KB-001 | `tae_knowledge_base.json` | `tae_knowledge_base.py` | **PRODUCED_NOT_CONSUMED** | Live governor only | — |
| CE-001 | `tae_confidence_evolution.json` | `tae_confidence_evolution.py` | **PARTIALLY_CONSUMED** | PDE, LTP, weights | BUY↓, SKIP↑, BUY weight −0.003 |
| DR-001 | `tae_decision_replay.json` | `tae_decision_replay_composer.py` | **PARTIALLY_CONSUMED** | PDE, LTP | DO_NOT_PROMOTE → BUY↓, SKIP↑ |
| PD-001 | `pattern_discovery_summary.txt` | `pattern_discovery_engine.py` | **PARTIALLY_CONSUMED** | PDE | +3 ROTATE if file exists |
| LM-001 | `adaptation_hints.json` | `tae_longitudinal_outcome_memory.py` | **FULLY_CONSUMED** | PDE, weights | All actions via hints + weights |
| LM-002 | `knowledge.json` | `tae_longitudinal_outcome_memory.py` | **PRODUCED_NOT_CONSUMED** | Day-0 baseline only | — |
| LM-003 | `decisions.jsonl` | `tae_longitudinal_outcome_memory.py` | **PARTIALLY_CONSUMED** | Memory index, validation feedback | Indirect |
| AW-001 | `paper_action_weights.json` | `tae_adaptive_paper_weights.py` | **FULLY_CONSUMED** | PDE | All 7 actions (score multipliers) |
| LTP-001 | `hypotheses.json` | `tae_learning_to_profit_bridge.py` | **FULLY_CONSUMED** | PDE, experiments | SKIP gates, hypothesis rules |
| LTP-002 | `experiment_results.json` | `tae_paper_experiment_runner.py` | **FULLY_CONSUMED** | PDE, weights, memory | experiment_boost, REJECT→SKIP |
| PDE-001 | `paper_decisions.json` | `tae_paper_decision_engine.py` | **FULLY_CONSUMED** | Validation, memory | Feedback loop |
| VAL-001 | `decision_validation_results.json` | `tae_dpe_paper_executor_infra.py` | **FULLY_CONSUMED** | Weights, memory, gate | Weights, promotion gate |
| DPE-001 | `evaluation.json` | `tae_dpe_result_evaluator.py` | **PARTIALLY_CONSUMED** | Loaded in PDE ctx, **not scored** | — |
| DPE-002 | `learning.json` | `tae_dpe_learning_engine.py` | **PARTIALLY_CONSUMED** | Adaptive selector, LTP | Indirect via adaptive.json |
| DPE-003 | `adaptive.json` | `tae_dpe_adaptive_selector.py` | **FULLY_CONSUMED** | PDE, weights | Philosophy ±3–5 action bias |
| GII-001 | `tae_growth_intelligence.json` | `tae_growth_intelligence.py` | **FULLY_CONSUMED** | PDE (primary) | Dominant scorer all actions |
| PPV-001 | `tae_profit_protection_validation.json` | `tae_profit_protection_validation.py` | **FULLY_CONSUMED** | PDE | PROTECT, REDUCE, SELL |
| APPE-001 | `tae_adaptive_profit_policy_engine.json` | APPE | **FULLY_CONSUMED** | PDE | BUY block, SKIP boost |
| PPG-001 | `tae_portfolio_profit_governor.json` | PPG | **FULLY_CONSUMED** | PDE | SELL, REDUCE, PROTECT |
| MPL-001 | `tae_market_philosophy_lab.json` | philosophy lab | **PRODUCED_NOT_CONSUMED** | DPE events only | — |
| RO-001 | `tae_recommendation_outcome.json` | meta intelligence | **STALE (213h)** | None | — |
| SR-001 | `tae_candidate_strategy_registry.json` | strategy evolution | **LEGACY (164h)** | None | — |
| LEG-001 | `adaptive_weights.csv` | committee runtime | **DUPLICATE** | Live committee only | Parallel to PAPER weights |

---

## 3. Specific Questions Answered

### 1. Do we already have a Knowledge Execution / Rule Materialization layer?

**Yes — fragmented across five modules, not unified:**

| Module | Role |
|---|---|
| `tae_knowledge_base.py` | Consolidates fade/discovery/confidence into `tae_knowledge_base.json` |
| `tae_decision_governor.py` | Live advisory materialization (NOT PDE) |
| `tae_longitudinal_outcome_memory.py` | PAPER hints + knowledge rules (hints consumed; rules not) |
| `tae_learning_to_profit_bridge.py` | Hypothesis + experiment queue materialization |
| `tae_adaptive_paper_weights.py` | Validation → capped action weight materialization |

**Missing:** unified rule→PDE mapper by `rule_id` / `pattern_type`.

### 2. Which file implements it?

No single file. Closest PAPER executors: `tae_adaptive_paper_weights.py` + `tae_paper_decision_engine.apply_learning_evidence_bias()`.

### 3–6. Named hypothesis reach

| Hypothesis | Materialization | adaptation_hints | paper_action_weights | paper_decisions |
|---|---|---|---|---|
| **SCORE_DECAY_SHADOW** | LTP queue (`PAPER_CONFIDENCE_SHADOW`) | No | No | Indirect via experiments only |
| **STOP_REENTRY_CHURN** | LTP queue (`LTB-CONF-STOP_REENTRY_CHURN`) | No | No | Indirect only |
| **MISSED_PROFIT_PROTECTION** | LTP queue + protection validation | No | No | Indirect via `protection_validation_bias` |
| **TRAILING_1_PROTECTION_HYPOTHESIS** | LTP queue + `best_strategy=shadow_trailing_1` | No | No | Indirect via protection validation |

**Aggregate path that DOES reach decisions:** `DO_NOT_PROMOTE` / `DO_NOT_PROMOTE_TO_LIVE` in stringified `final_recommendation` → PDE −12 BUY, +10 SKIP; weights −0.003 BUY.

**X.KNOWLEDGE-1C:** documented in confidence evolution as recommended next module — **not implemented**.

### 7–9. Strategy / meta learning

| Output | Consumed? |
|---|---|
| Strategy evolution recommendations | **Report-only** (`research_core/strategy_evolution/`) |
| Candidate strategy registry | **Report-only / stale (164h)** |
| Recommendation outcome learning | **Report-only / stale (213h)** |

### 10–13. Do rules/weights/recommendations change scores?

| Question | Answer |
|---|---|
| Knowledge rules change PAPER scores? | **Partially** — only via `adaptation_hints` aggregates, not `knowledge.json` text |
| Adaptive weights change scores? | **Yes** — verified 25/25 decisions with `adaptive_weight_evidence` |
| Rejected recommendations penalize? | **Yes** — REJECT verdict → weight ↓; NEEDS_MORE_DATA → slight ↓ |
| Successful recommendations boost? | **Yes** — PROMISING/CONTINUE → weight ↑ (capped ±0.02/day) |

### 14. Important learning not used anywhere in PAPER path?

- `tae_knowledge_base.json` (richest consolidated rules)
- `runtime_outputs/longitudinal_memory/knowledge.json`
- `runtime_outputs/dpe/result_evaluator/evaluation.json` (loaded, never scored)
- `tae_recommendation_outcome.json` (stale)
- `tae_candidate_strategy_registry.json` (stale)
- `tae_market_philosophy_lab.json` (DPE path only)

---

## 4. PAPER Decision Engine — Consumption Map

```
build_context() loads:
  ✅ GII, PPG, APPE, shadow, shadow_validation
  ✅ DPE adaptive, DPE eval (loaded but unused in scoring)
  ✅ LTP hypotheses + experiments
  ✅ confidence_evolution, decision_replay
  ✅ adaptation_hints, paper_action_weights
  ❌ knowledge_base, knowledge.json, DPE learning, philosophy lab

score_actions_for_ticker() applies:
  ✅ GII lifecycle/strategy/cap_eff (dominant)
  ✅ PPG posture, APPE policy
  ✅ Horizon bias, stale penalty
  ✅ apply_learning_evidence_bias (aggregate caution)
  ✅ apply_adaptive_paper_weights (all actions)
  ✅ protection_validation_bias
  ✅ experiment_boost + apply_hypothesis_rules
  ✅ DPE philosophy ±3–5
```

**Cycle ordering note:** `full-paper-cycle` runs `paper-decisions` before `adaptive-weights` in the same run → same-day PDE uses **previous run's weights** (one cycle lag).

---

## 5. Missing Wiring Backlog

### P0 — Critical learning exists but does not influence PAPER decisions

| ID | Gap | Minimal wiring |
|---|---|---|
| **GAP-P0-001** | `tae_knowledge_base.json` not in PDE | Load in `build_context()`; map `pattern_type` → action deltas |
| **GAP-P0-002** | `knowledge.json` unused | Feed rules into `build_adaptation_hints()` or weight deltas |
| **GAP-P0-003** | DPE eval winner unused in scoring | Use `ctx['dpe_eval'].winner` in `score_actions_for_ticker()` |
| **GAP-P0-004** | Same-cycle weight lag | Run adaptive-weights **before** paper-decisions, or re-run PDE after weights |

### P1 — Influences decisions weakly or indirectly

| ID | Gap | Minimal wiring |
|---|---|---|
| **GAP-P1-001** | Named hypotheses not parsed | Read `confidence_evolution_entries[].hypothesis` by name in PDE |
| **GAP-P1-002** | DPE learning not in weights | Add regime pattern delta from `learning.json` |

### P2 — Report-only useful evidence

| ID | Gap |
|---|---|
| **GAP-P2-001** | `pattern_discovery_summary.txt` — existence flag only (+3 ROTATE) |

### P3 — Legacy / archived

| ID | Gap |
|---|---|
| **GAP-P3-001** | `tae_recommendation_outcome.json`, `tae_candidate_strategy_registry.json` — stale, no PAPER wire |
| **LEG-001** | `adaptive_weights.csv` duplicates PAPER weights file |

---

## 6. Final Recommendation

### **Start 30-day PAPER validation now — schedule P0 wiring in parallel**

**Rationale:**

The **operational feedback loop is working:**
- Decision validation → adaptive weights → PDE scoring (verified)
- Longitudinal memory accumulating (25 records)
- Promotion lock enforced (`live_promotion_allowed=false`)
- Forbidden files untouched

**However, do not assume the full knowledge stack is consumed.** Consolidated knowledge (`tae_knowledge_base.json`, `knowledge.json`, named confidence rules) remains **report-only or indirect** until P0 gaps are wired.

**Recommended sequence:**

1. **Day 0–1:** Run `python3 tae.py full-paper-cycle` daily (already baselined)
2. **Before Day 7:** Wire GAP-P0-004 (cycle ordering) — smallest change, immediate same-day feedback
3. **Before Day 14:** Wire GAP-P0-001 + GAP-P0-002 (knowledge → PDE/weights)
4. **Before Day 21:** Wire GAP-P0-003 (DPE eval winner → PDE)

No new engines required — only consumption wiring in existing modules.

---

## 7. Duplicates / Legacy

| Pair | Status |
|---|---|
| `adaptive_weights.csv` vs `paper_action_weights.json` | **DUPLICATE domain** — live committee vs PAPER |
| `tae_decision_governor.py` vs `tae_paper_decision_engine.py` | **Parallel governors** — knowledge consumed live-only |
| `research_core/evolution/strategy_evolution.py` vs `strategy_evolution/daily_runner.py` | **Legacy superseded** |
| Strategic allocation vs APPE | **Legacy vs active** — APPE is PDE input |

---

*Audit complete. No code changes made. No commit performed.*
