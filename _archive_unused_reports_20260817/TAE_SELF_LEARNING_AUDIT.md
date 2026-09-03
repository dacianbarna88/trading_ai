# TAE Self-Learning Audit (READ-ONLY)

**Generated:** 2026-07-23  
**Mode:** `READ_ONLY` — no code, config, economic state, or LaunchAgent changes  
**Scope:** Full repository static analysis + existing artifacts + isolated unit tests only  

---

## 1. Executive Verdict

| Dimension | Verdict |
|-----------|---------|
| **Self-learning** | `SELF_LEARNING_PARTIALLY_CONNECTED` |
| **Economic learning** | `ECONOMIC_FEEDBACK_CONNECTED_BUT_VALUE_NOT_PROVEN` |
| **Self-improvement** | `CHALLENGER_INFRASTRUCTURE_ONLY` (with narrow semi-automatic ROI paper flag) |
| **Autonomy** | `HUMAN_GOVERNED_AUTONOMY` |

**Decision impact proven (PAPER PDE):** **true** — adaptive weights and longitudinal knowledge multiply/add scores before argmax.  
**Economic value of learning proven:** **false** — ablation verdict `LEARNING_ATTRIBUTION_INCONCLUSIVE`; RAP uplift NOT_PROVEN.  
**Automatic runtime of learning loop:** **partial** — via `full-paper-cycle` / structural governance when invoked; **not** a dedicated LaunchAgent for learning.  
**Challenger generation automatic:** **false** (manual/hardcoded + research generators).  
**Promotion eligibility proven:** **partial** (`PROMOTE_TO_LIVE_CANDIDATE` / ROI `PROMOTED_PAPER` for paper REDUCE only).  
**Automatic promotion to LIVE/canonical:** **false** — hard lock.

---

## 2. Definitions used

See mission brief §DEFINITIONS (A–E). Summary:

- **Authentic self-learning** requires feedback → persistent state → read-back → demonstrable future decision change.
- **Continuous learning** requires that loop to run repeatedly without code edits each cycle.
- **Economic learning** requires economic outcomes in the feedback, not only internal scores.
- **Self-improvement** requires detect → hypothesize → challenger → validate → materiality → formal promotion eligibility.
- **Full autonomy** requires promotion without humans; human-gated promotion ⇒ controlled autonomy.

---

## 3. Architecture (as demonstrated)

### Canonical PAPER learning path (CONNECTED wiring)

```text
paper decisions (PDE)
  → paper execution / validation / rule_outcome_attribution
  → [pre_pde_feedback in tae_full_paper_cycle]
       longitudinal_memory → knowledge.json + adaptation_hints.json
       adaptive_paper_weights → paper_action_weights.json
       rule_survival → rule_lifecycle.json
  → PDE score_actions_for_ticker
       apply_adaptive_paper_weights   (scores *= mult)
       apply_longitudinal_knowledge_bias (scores += delta)
       apply_rule_lifecycle_bias
       (+ soft: confidence, DPE evaluator, experiments, PPG/APPE)
  → paper_decisions.json
  → optional post-learning re-PDE + changed-ticker execution
```

### LIVE path (NOT connected to paper learning stack)

```text
live_bot.py
  ← tae_live_advisory.json (BUY block only)
  ✗ does not import adaptive weights / longitudinal / rule lifecycle
```

### Parallel PAPER V1/V2

Isolated A/B harness (`CANONICAL_PAPER_MIRROR` + `ISOLATED_PARALLEL_PAPER`).  
Daemon can run on a schedule; it is **not** an automatic self-improvement inventor.

---

## 4. Call graph (critical edges)

| Edge | Caller → Callee | Classification |
|------|-----------------|----------------|
| Orchestrate learning refresh | `tae_full_paper_cycle.run_pre_pde_feedback` → `run_longitudinal_memory`, `run_adaptive_paper_weights`, `run_rule_survival` | **CONNECTED** |
| Weights → scores | `apply_adaptive_paper_weights` → `scores[action] *= mult` | **CONNECTED** |
| Knowledge → scores | `apply_longitudinal_knowledge_bias` | **CONNECTED** |
| Lifecycle → scores | `apply_rule_lifecycle_bias` | **CONNECTED** |
| Attribution → survival | `tae_paper_execution` rule attribution → `tae_rule_survival` | **CONNECTED** |
| Post-learning evolution | `run_post_learning_evolution` / structural governance | **CONNECTED** (same-cycle) |
| Committee → PDE | profit committee/memory | **SHADOW_ONLY** (except PPG posture leakage) |
| Event memory → PDE | event memory store | **SHADOW_ONLY / scaffold** |
| Learning → live_bot | — | **DEAD** |
| Ablation → production weights | `tae_learning_economic_ablation` | **REPORT_ONLY** (by design) |
| ROI-001 → paper REDUCE | queue `PROMOTED_PAPER` → paper execution flag | **PARTIALLY_CONNECTED** |
| Challenger C1–C5 → production | hardcoded replay | **REPORT_ONLY** |
| Live promotion | `tae_live_promotion_lock` | **LOCKED** (`machine_live_promotion_allowed=false`) |

---

## 5. Component inventory (summary)

| Component | Path | Called | Runtime | Persistent | Changes decisions | Class |
|-----------|------|-------:|--------:|-----------:|------------------:|-------|
| Adaptive paper weights | `tae_adaptive_paper_weights.py` | yes | paper cycle | `paper_action_weights.json` | yes (×) | CONNECTED |
| Longitudinal memory | `tae_longitudinal_outcome_memory.py` | yes | paper cycle | `knowledge.json`, hints | yes (+) | CONNECTED |
| Rule survival | `tae_rule_survival.py` | yes | paper cycle | `rule_lifecycle.json` | yes | CONNECTED |
| Paper Decision Engine | `tae_paper_decision_engine.py` | yes | paper | decisions JSON | is the decision | CONNECTED |
| Full paper cycle | `tae_full_paper_cycle.py` | CLI/ops | when run | many | yes | CONNECTED |
| DPE learning/adaptive | `tae_dpe_learning_engine.py`, `tae_dpe_adaptive_selector.py` | CLI/gate | soft | `dpe/learning`, `dpe/adaptive` | soft | PARTIAL |
| LTP bridge / experiments | `tae_learning_to_profit_bridge.py`, `tae_paper_experiment_runner.py` | CLI | when run | experiment queue/results | conditional | PARTIAL |
| Confidence evolution | `tae_confidence_evolution.py` | morning/PDE | when run | JSON | named rules | PARTIAL |
| Profit committee/memory/context | `tae_profit_*` | protect CLI | shadow | JSON | direct: no | SHADOW |
| Decision governor | `tae_decision_governor.py` | morning | advisory | JSON | live enrich only | SHADOW |
| Live advisory | `live_advisory_*.py` | live_bot | active | `tae_live_advisory.json` | BUY block | PARTIAL (live only) |
| Learning ablation | `tae_learning_economic_ablation.py` | CLI | research | ablation dir | no SSOT write | REPORT |
| ROI-001 challenger | `tae_roi001_challenger.py` | CLI | optional | queue JSON | REDUCE sizing | PARTIAL |
| Profit recovery / baseline challengers | `tae_profit_recovery_challengers.py`, `tae_profit_optimization.py` | CLI | audit | reports | no auto | REPORT |
| Strategy evolution | `research_core/strategy_evolution/` | research | when run | candidates | review-only | PARTIAL |
| Hypothesis generators | `research_core/hypothesis/` | research | when run | research JSON | not PDE | RESEARCH |
| Event memory | `tae_event_memory*` | demo/advisory | scaffold | JSON (0 events) | no | SHADOW |
| Legacy CSV weights | `adaptive_weights.csv` | committee legacy | stale | CSV | not PDE | LEGACY |
| research_core LearningEngine | `research_core/learning/` | demos | research | reports | no | DEAD for PDE |
| Parallel PAPER V1/V2 | `tae_parallel_paper_*` | daemon/CLI | HEALTHY | parallel state | A/B only | INFRA |

---

## 6. Capability matrix

| Capability | Exists in code | Called | Runtime active | Persistent | Changes decisions | Economic attribution | Autonomous | Verdict |
|------------|---------------:|-------:|---------------:|-----------:|------------------:|---------------------:|-----------:|---------|
| outcome capture | yes | yes | paper | yes | via attribution | partial | no | PARTIAL |
| decision attribution | yes | yes | paper | yes | via lifecycle/weights | yes (IDs) | no | CONNECTED |
| post-trade learning | yes | via cycle | when cycle runs | yes | yes | inconclusive | semi | PARTIAL |
| adaptive weights | yes | yes | paper cycle | yes | **yes** | inconclusive | semi | CONNECTED |
| longitudinal memory | yes | yes | paper cycle | yes | **yes** | inconclusive | semi | CONNECTED |
| threshold adaptation | limited | rare | soft | yes | soft | no | no | PARTIAL |
| policy adaptation (APPE) | yes | shadow→PDE soft | soft | yes | soft | no | no | PARTIAL |
| decision feedback loop | yes | yes | paper | yes | yes | inconclusive | semi | CONNECTED (paper) |
| replay learning | yes | CLI | research | yes | not auto | reports | no | REPORT |
| confidence calibration | yes | yes | soft | yes | named rules | no | no | PARTIAL |
| regime learning | fragmented | soft | soft | yes | soft | no | no | PARTIAL |
| ticker-specific learning | yes (ticker adj) | yes | paper | yes | yes | weak | no | PARTIAL |
| challenger generation | hardcoded/manual | CLI | no scheduler | reports | no auto invent | reports | no | MANUAL |
| challenger validation | yes | CLI | when run | reports | ROI narrow | yes/inconclusive | no | SEMI |
| materiality gate | yes (parallel/ROI) | yes | partial | yes | gates verdicts | yes | no | PARTIAL |
| promotion eligibility | yes | lock/ROI | yes | yes | candidate only | n/a | no | HUMAN_GATE |
| promotion execution (LIVE) | blocked | lock | lock | lock | never auto | n/a | no | ABSENT |
| rollback | partial docs/code | rare | no | — | — | — | no | WEAK |
| self-diagnosis | health/quick health | yes | yes | JSON | advisory | no | semi | PARTIAL |
| hypothesis generation | research | research | when run | research | not PDE | no | no | RESEARCH |

---

## 7. Evidence of self-learning (A)

| Criterion | Paper | Live |
|-----------|-------|------|
| Feedback from own decisions | yes (validation, attribution, longitudinal) | advisory regen ≠ outcome→weight |
| Persistent state update | yes (`paper_action_weights.json`, `knowledge.json`, …) last **2026-07-22** | `tae_live_advisory.json` only |
| State read later | yes (PDE `build_context`) | advisory load |
| Changes future decision | **PROVEN in code** (`scores *= mult`, ablation 17/25 action flips) | BUY block only |

**Journaling alone ≠ learning:** many shadow modules journal without PDE consume.

---

## 8. Decision-impact proof

### Code proof

```1268:1284:tae_paper_decision_engine.py
def apply_adaptive_paper_weights(...):
    ...
        if mult != 1.0:
            scores[action] *= mult
```

```332:351:tae_full_paper_cycle.py
def run_pre_pde_feedback(...):
    ...
    mem_result = run_longitudinal_memory()
    weights_result = run_adaptive_paper_weights()
```

### Ablation proof (existing artifact, not re-run)

`tae_learning_ablation_summary.json`:

- `decisions_changed`: **17 / 25** (68%)
- `pnl_attributable_to_learning`: **0**
- `matured_attribution_n`: **0**
- `verdict`: **LEARNING_ATTRIBUTION_INCONCLUSIVE**

### Unit tests run this audit (isolated)

- `tae_adaptive_paper_weights_test.py` — **8 OK** (weight math/persistence; does not prove argmax flip alone)

### Missing ideal proof

No dedicated unit test: *identical market features + weight set A → action X; weight set B → action Y*. Ablation CSV is the strongest decision-impact evidence.

---

## 9. Economic attribution

| Question | Answer |
|----------|--------|
| Can learning change decisions? | **Yes (PAPER)** |
| Can we attribute matured PnL to learning? | **NOT_PROVEN** (`matured_attribution_n=0`) |
| RAP / Learning RAP | **NOT_PROVEN** (Chapter 5 / ablation language) |
| Economic value verdict | **NOT_MEASURED / INCONCLUSIVE** |

Allowed classification used: `ECONOMIC_FEEDBACK_CONNECTED_BUT_VALUE_NOT_PROVEN`.

---

## 10. Runtime orchestration

| Mechanism | Learning? | Challenger? | Notes |
|-----------|-----------|-------------|-------|
| `full-paper-cycle` / structural governance | **yes** when run | no | primary learning orchestrator |
| `com.tradingai.parallel-paper` | no (A/B only) | no | V1/V2 daemon |
| market-session-guard / market-open / startup | no learning update | no | ops |
| cron paper MTM / scanner | no learning | no | |
| `daily_intelligence_runner` | legacy warn | — | stripped from install schedule |
| Challenger/ROI/ablation CLIs | manual | manual | **no LaunchAgent** |

**Continuous learning:** exists **if and when** paper cycle runs repeatedly; not a dedicated always-on learning daemon.

---

## 11. Challenger / promotion

| Item | Mode |
|------|------|
| Challenger generation | **MANUAL** / hardcoded (+ research semi-auto hypotheses) |
| Parallel V1/V2 | **Manually built A/B infra**, not auto self-improver |
| Validation | CLI/replay/ROI gates |
| Promotion eligibility | `PROMOTE_TO_LIVE_CANDIDATE`; ROI `PROMOTED_PAPER` (paper REDUCE) |
| Auto LIVE promotion | **ABSENT** — `machine_live_promotion_allowed=false` |
| Should auto-promote without human? | **No** (governance correct); controlled autonomy is appropriate |

Self-improvement verdict: `CHALLENGER_INFRASTRUCTURE_ONLY` (not a closed detect→promote loop).

---

## 12. Duplicates / passive complexity

| Group | Authority | Shadow / unused risk |
|-------|-----------|----------------------|
| Adaptive weights | `paper_action_weights.json` + PDE | Legacy `adaptive_weights.csv` still exists |
| Memory | longitudinal → PDE | event memory scaffold; profit memory shadow |
| Attribution | rule attribution + ablation | RAP docs without closed controller |
| Decision owners | PDE paper; live_bot live | governors/committee shadow; parallel V2 isolated |
| Promotion | live lock | multiple “candidate” wordings |

**Passive complexity:** many named learning modules; few are on the canonical PDE path.

---

## 13. Risks

1. **False confidence:** modules named “learning” that never reach PDE.  
2. **Decision change ≠ profit:** ablation shows action flips without matured economic RAP.  
3. **Overfitting / small-n:** weights update from limited validation samples; caps exist (0.85–1.15, daily delta).  
4. **Contamination:** challenger validation must not leak into canonical book (parallel PAPER helps).  
5. **Live disconnect:** paper learning never trains live_bot selection.  
6. **Orchestration fragility:** learning only advances when paper cycle is run.

---

## 14. Final verdict

TAE has a **real, partially connected PAPER self-learning loop** (outcome artifacts → weights/memory/lifecycle → PDE scores → different actions).  

It does **not** have:

- proven economic value of that learning;
- a continuous always-on learning daemon independent of paper cycle;
- automatic challenger invention + economic promotion;
- automatic LIVE promotion (correctly locked).

---

## 15–17. Exists / unconnected / missing

**Exists and connected (paper):** adaptive weights, longitudinal knowledge, rule lifecycle, PDE consumer, paper-cycle orchestration, ablation harness.

**Built but unconnected / shadow:** profit committee learning, event memory, most challenger sims, research LearningEngine, legacy CSV weights, LIVE path.

**Truly missing for controlled self-improvement complete:** automatic degradation→hypothesis→challenger factory; matured economic RAP with sample gates; formal promotion package that stops at human approval with rollback playbook wired to runtime.

---

## Limitations of this audit

- Did not re-run full-paper-cycle or economic ablation (would write artifacts).  
- Did not prove a pure unit-level weight A/B action flip beyond ablation CSV.  
- Parallel PAPER and LIVE were inspected read-only; no trades executed.  
- “Not found in call graph” for obscure modules may miss dynamic imports — marked UNKNOWN only where relevant; main PDE path was statically confirmed.
