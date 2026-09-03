# TAE Self-Improvement Component Wiring Audit

```text
AUDIT_ID=TAE_SELF_IMPROVEMENT_COMPONENT_WIRING_AUDIT
BRANCH=cursor/x12b-legacy-archive-hotfix
HEAD=9e86a982319d42b8de78afb0df017eb0da99de41
MODE=READ_ONLY
CODE_CHANGED=false
COMMIT_CREATED=false
RUNTIME_MUTATED=false
```

## Verdict

**SELF_IMPROVEMENT_LOOP_PARTIALLY_WIRED_ATTRIBUTION_TO_PROPOSAL_BREAK**

TAE already has most lifecycle *pieces*. It does **not** have a closed autonomous path:

```text
loss/outcome → attribution → learning → hypothesis → experiment →
challenger → replay → economic evaluation → Strategy Lab →
human approval → promotion → runtime feedback
```

What is closed today is a **PAPER scoring loop**:

```text
outcomes → longitudinal memory + adaptive weights → PDE scoring → next decisions
```

What is broken for self-improvement proper is:

```text
attribution / ablation / forward evidence
        ✗ does not feed
hypothesis / own improvement proposal
```

`AUTONOMOUS_IMPROVEMENT_PROPOSAL=false`

---

## Target loop coverage

| Stage | Exists | Connected | Artifact-only | CLI | Schedule | Status |
|---|---|---|---|---|---|---|
| loss/outcome | YES | YES (PAPER) | parallel journals weak | YES | YES (FPC/daemon) | PARTIAL |
| attribution | YES | NO to proposals | YES for decisions | YES | NO full run | BREAK |
| learning | YES | YES to PDE | NO | YES | YES | ACTIVE |
| hypothesis | YES | YES from GII/DPE/etc | CIO provisional only | YES | YES (FPC) | PARTIAL |
| experiment proposal | YES | YES | synthetic scoring | YES | YES | SHADOW |
| candidate/challenger | YES | PARTIAL | research challengers | PARTIAL | PARTIAL | PARTIAL |
| replay | YES | WEAK | promotion audit | NO dedicated | NO | WEAK |
| economic evaluation | YES | NO mutation | YES | YES | NO | REPORT |
| Strategy Lab | YES | observe/human | apply≠books | YES | NO FPC | SHADOW |
| human approval | YES | Lab tickets | CIO forbidden | YES | NO | LAB_ONLY |
| promotion | YES | LIVE lock | Lab apply metadata | YES | YES lock | LOCKED |
| runtime feedback | YES | weights YES | CIO observe | YES | YES | PARTIAL |

---

## Stage-by-stage wiring

### 1. loss / outcome — EXISTS, CONNECTED (PAPER)

| Component | Location | Caller | Consumer | CLI | Schedule | Status |
|---|---|---|---|---|---|---|
| Paper execution + rule outcome attribution | `tae_paper_execution.py` → `runtime_outputs/paper_execution/rule_outcome_attribution.json` | FPC, governance | adaptive weights, longitudinal | `paper-execution` | FPC | ACTIVE_CANONICAL |
| Decision validation outcomes | `runtime_outputs/paper_decisions/decision_validation_results.json` | PDE/validation | adaptive weights, memory | `paper-decisions` | FPC | ACTIVE_CANONICAL |
| Parallel V1/V2 learning events | `record_execution_learning_feedback` → `.../journals/learning_events.jsonl` | parallel daemon | CIO watch only | parallel cmds | daemon | ACTIVE_SHADOW / ARTIFACT for CLR |
| Hard-risk post-exit | `tae_longitudinal_outcome_memory.py` | CLR / outcome-memory | knowledge | `outcome-memory` | FPC/CLR | ACTIVE_CANONICAL |

**Break:** parallel learning journals do **not** enter `run_canonical_learning_cycle` proposal inputs.

### 2. attribution — EXISTS, NOT CONSUMED FOR PROPOSALS

| Component | Location | Caller | Consumer | CLI | Schedule | Status |
|---|---|---|---|---|---|---|
| Learning economic attribution | `tae_learning_economic_attribution_engine.run_attribution` | CLI / `__main__` | CIO/Lab read; **no proposer** | `learning-attribution-*` | **NO** | RESEARCH_ONLY / ARTIFACT_ONLY |
| Forward evidence monitor | `observe_forward_evidence` | learning daemon | CIO digest | via status CLI | LaunchAgent 900s | ACTIVE_SHADOW |
| Learning ablation | `tae_learning_economic_ablation.run_ablation` | CLI | reports | `learning-economic-ablation` | NO | RESEARCH_ONLY |
| Parallel paper economic attribution | `tae_paper_economic_attribution.py` | parallel runtime | Strategy Lab economics adapter | none dedicated | parallel | ACTIVE_SHADOW |

**Primary break evidence:** `tae_learning_to_profit_bridge.load_sources()` loads GII, PPG, APPE, DPE, decision_replay, confidence — **not** attribution, ablation, or forward-learning JSON.

Daemon calls **`observe_forward_evidence` only**, not `run_attribution`.  
`run_attribution` is **not** in `tae_full_paper_cycle.CYCLE_STEPS`.

### 3. learning — EXISTS, CONNECTED TO PDE

| Component | Location | Caller | Consumer | CLI | Schedule | Status |
|---|---|---|---|---|---|---|
| Canonical learning runtime | `tae_canonical_learning_runtime.run_canonical_learning_cycle` | FPC pre-PDE, daemon, CLI | weights/knowledge SSOT | `learning-runtime-*` | LaunchAgent | ACTIVE_CANONICAL |
| Longitudinal memory | `run_longitudinal_memory` | CLR, FPC | PDE `apply_longitudinal_knowledge_bias` | `outcome-memory` | YES | ACTIVE_CANONICAL |
| Adaptive paper weights | `run_adaptive_paper_weights` | CLR, FPC | PDE `apply_adaptive_paper_weights` | `adaptive-weights` | YES | ACTIVE_CANONICAL |
| Rule survival | `run_rule_survival` | CLR | survival reports / soft learning | strategy-survival | YES | ACTIVE_CANONICAL |
| DPE learning | `tae_dpe_learning_engine.py` | FPC | DPE adaptive / morning score | `dpe-learning` | FPC | ACTIVE_CANONICAL |

CLR explicit scope: longitudinal + adaptive weights + rule survival.  
**Not** attribution → hypothesis → challenger.

### 4. hypothesis — EXISTS, WRONG INPUTS FOR SELF-IMPROVEMENT

| Component | Location | Caller | Consumer | CLI | Schedule | Status |
|---|---|---|---|---|---|---|
| Learning-to-Profit bridge | `tae_learning_to_profit_bridge.py` → `hypotheses.json` + queue | FPC, governance | paper-experiments | `learning-profit` | FPC | ACTIVE_CANONICAL |
| Research hypothesis stack | `research_core/hypothesis/*` | demos | research stores | none | none | RESEARCH_ONLY |
| CIO provisional learnings | `tae_today_cio_extension._learning_closure` | `today --cio` | human report | `today --cio` | none | ARTIFACT_ONLY |

Hypotheses exist, but they are **not** generated from validated economic attribution of losses.

### 5. experiment proposal — EXISTS, SYNTHETIC

| Component | Location | Caller | Consumer | CLI | Schedule | Status |
|---|---|---|---|---|---|---|
| Paper experiment runner | `tae_paper_experiment_runner.score_hypothesis` | FPC | capital challenger / weights aggregation | `paper-experiments` | FPC | ACTIVE_SHADOW |
| LTP queue | `runtime_outputs/learning_to_profit/paper_experiment_queue.jsonl` | learning-profit | experiment runner | via learning-profit | FPC | ACTIVE_CANONICAL |

**Break:** scoring is heuristic, not fill-level portfolio replay / matured RAP.

### 6. candidate / challenger — PARTIAL

| Component | Location | Caller | Consumer | CLI | Schedule | Status |
|---|---|---|---|---|---|---|
| Capital challengers | `update_capital_challenger_registry` | structural governance | PDE elevate | **none dedicated** | governance | ACTIVE_CANONICAL |
| ROI-001 challenger | `tae_roi001_challenger.py` | governance / paper_execution flags | REDUCE when `PROMOTED_PAPER` | **none in dispatcher** | governance | ACTIVE_SHADOW |
| Adaptive deployment canary | `tae_adaptive_deployment.py` | CLI / parallel hooks | sizing | `adaptive-deployment` | operator | ACTIVE_SHADOW |
| Research candidate registry | `research_core/strategy_evolution/candidate_registry.py` | demos | Lab research adapter RO | none | optional demo | RESEARCH_ONLY |

### 7. replay — WEAK

| Component | Location | Caller | Consumer | CLI | Schedule | Status |
|---|---|---|---|---|---|---|
| Decision replay composer | `tae_decision_replay_composer.py` | market-open runner | LTP/PDE advisory | **no dispatcher cmd** | weak | ACTIVE_SHADOW |
| Decision replay promotion | `tae_decision_replay_promotion.py` | tests/`__main__` | reports | none | none | ARTIFACT_ONLY |
| Chronological portfolio replay | `tae_chronological_portfolio_replay.py` | manual/tests | Lab ReplayAdapter | none | none | RESEARCH_ONLY |
| Ablation as counterfactual | `tae_learning_economic_ablation.py` | CLI | reports | YES | none | RESEARCH_ONLY |

### 8. economic evaluation — REPORT RICH, DECISION POOR

| Component | CLI | Runtime mutation | Status |
|---|---|---|---|
| Attribution / ablation / ROI reports | attribution/ablation CLIs; ROI script | NO | REPORT |
| Profit optimization | `profit-optimization` | NO | RESEARCH_ONLY |
| Conversion breakthrough | `conversion-breakthrough` | NO | RESEARCH_ONLY |
| Opportunity attrition | `opportunity-attrition` | NO | RESEARCH_ONLY |
| Investment council | `investment-council` | NO (synthesis) | ACTIVE_SHADOW / BREAK to PDE |

### 9. Strategy Lab — EXISTS, HUMAN-GATED, OBSERVE

| Component | CLI | Mutates books? | In FPC? | Status |
|---|---|---|---|---|
| Façade / adapters / scoreboard | `strategy-lab*` | NO | NO | ACTIVE_SHADOW |
| Registry | config + status | identity only | NO | ACTIVE_CANONICAL identity |
| Promotion domain | ticket/approve/apply/rollback | Lab state only; `books_written=false` | NO | ACTIVE_SHADOW |

### 10. human approval — LAB ONLY

- Strategy Lab tickets: real human gate for Lab domain.
- CIO learning closure: `IMPLEMENTATION_ALLOWED=false`, `validated_learnings=[]`.
- Investment council: operator brief; not a PDE caller.

### 11. promotion — LOCK STRONG, APPLY WEAK

| Component | Effect | Status |
|---|---|---|
| `promotion-lock` / `enforce_promotion_gate` | `live_promotion_allowed=false` always | ACTIVE_CANONICAL safety |
| FPC `build_promotion_gate` | advisory + lock feed | ACTIVE_CANONICAL deny LIVE |
| ROI `PROMOTED_PAPER` | can affect PAPER REDUCE | ACTIVE_SHADOW |
| Strategy Lab `apply_ticket` | champion metadata; not PDE/books | BREAK to runtime |

### 12. runtime feedback — WEIGHTS YES, PROPOSALS NO

| Component | Connected? | Notes |
|---|---|---|
| PDE `apply_adaptive_paper_weights` / `apply_longitudinal_knowledge_bias` | YES | Closes scoring loop |
| Paper execution ROI flags | PARTIAL | REDUCE when promoted |
| Parallel learning → CLR | NO | Isolation break |
| `today --cio` | OBSERVE ONLY | No proposal apply |
| `live_bot` learning imports | NO | LIVE not on loop |

---

## Where the path breaks: loss → own improvement proposal

```text
1. Loss recorded in paper_execution / validation
        ↓ CONNECTED
2. CLR updates longitudinal memory + adaptive weights
        ↓ CONNECTED
3. PDE scoring changes
        ↓ CONNECTED
4. Next PAPER decisions change softly
        ✗ THIS IS ADAPTATION, NOT SELF-IMPROVEMENT PROPOSAL

Meanwhile, in parallel:

A. Attribution / ablation / forward evidence artifacts
        ✗ BREAK: not in load_sources()
B. Hypotheses from GII/PPG/DPE (not from validated loss attribution)
        ↓ CONNECTED
C. Synthetic paper-experiments
        ✗ BREAK: not matured economic replay
D. Soft capital challengers / optional ROI REDUCE
        ✗ BREAK: not Lab ticket / not human package from attribution
E. Strategy Lab recommend/ticket/apply
        ✗ BREAK: apply ≠ books/PDE
F. LIVE promotion
        ✗ HARD LOCK by design
G. today --cio learning closure
        ✗ IMPLEMENTATION_ALLOWED=false
```

**Exact primary rupture:**

```text
ATTRIBUTION_TO_HYPOTHESIS
```

Economic loss attribution exists as measurement infrastructure, but nothing converts a validated attribution verdict into an owned improvement proposal that Strategy Lab / human approval can act on.

---

## What exists vs what is only artifact

### Connected (used by PAPER decisions)

- paper execution outcomes
- longitudinal memory
- adaptive weights
- PDE apply_* consumers
- learning-profit → paper-experiments → capital challengers (soft)
- ROI production flags (narrow)
- LIVE promotion lock (deny)

### Exists + CLI, but artifact/report for decisions

- `learning-attribution-*`
- `learning-economic-ablation`
- `profit-optimization`
- `conversion-breakthrough`
- `opportunity-attrition`
- `investment-council`
- `today --cio` learning closure
- Strategy Lab scoreboard/explain (unless human manually tickets)

### Exists, no dedicated CLI

- ROI-001 runner (governance/script)
- decision-replay composer
- capital challenger registry updater

### Exists, no FPC/schedule

- full `run_attribution`
- ablation
- Strategy Lab suite
- `today --cio`

---

## Schedules

| Schedule | Runs | Missing for self-improvement |
|---|---|---|
| FPC `CYCLE_STEPS` | learning-profit, PDE, execution, experiments, outcome-memory, adaptive-weights, DPE learning, morning-audit | attribution-run, ablation, strategy-lab, today --cio |
| Canonical learning LaunchAgent (900s) | CLR cycle + `observe_forward_evidence` | `run_attribution`, hypothesis from attribution |
| Structural governance | LTP, memory, weights, capital challenger, ROI orch, promotion lock, council | attribution→proposal factory |
| Parallel daemon | V1/V2 journals + arm attribution | bridge into CLR/LTP |

---

## Recommended direction (no new system)

`NEW_LEARNING_ENGINE_REQUIRED=false`  
`NEW_REPORTING_SYSTEM_REQUIRED=false`

If later extended (not done in this audit):

1. Reuse `learning-attribution` / forward / ablation digests as **inputs** to an existing proposal surface (`learning-profit` or Strategy Lab `recommend`).
2. Keep measurement engines measurement-only unless explicitly human-gated.
3. Keep LIVE promotion lock.
4. Keep Strategy Lab human-gated; do not auto-apply to books.
5. Do not treat one-day V1/V2 relative PnL as validated learning (already enforced in `today --cio`).

---

## Final flags

```text
COMPONENTS_EXIST=true
LOOP_FULLY_WIRED=false
AUTONOMOUS_IMPROVEMENT_PROPOSAL=false
ATTRIBUTION_EXISTS=true
ATTRIBUTION_CONSUMED_BY_HYPOTHESIS=false
LEARNING_TO_PDE_CONNECTED=true
STRATEGY_LAB_EXISTS=true
STRATEGY_LAB_APPLIES_TO_BOOKS=false
HUMAN_APPROVAL_EXISTS=true
LIVE_PROMOTION_ALLOWED=false
CIO_IMPLEMENTATION_ALLOWED=false
PRIMARY_BREAK=ATTRIBUTION_TO_HYPOTHESIS
FINAL_VERDICT=SELF_IMPROVEMENT_LOOP_PARTIALLY_WIRED_ATTRIBUTION_TO_PROPOSAL_BREAK
```

Companion JSON: `tae_self_improvement_component_wiring_audit.json`
