# TAE Existing Conflict Resolution / Scenario Engine Audit

**Generated:** 2026-07-08T18:34:00+00:00  
**Mode:** READ_ONLY — no code changes, no commit  
**Branch context:** `cursor/x12b-legacy-archive-hotfix` (post structural governance + Investment Council synthesis)

---

## Final Verdict

### **EXISTS_AS_FRAGMENTED_COMPONENTS**

TAE already implements **most of the underlying capabilities** (action scoring, EV-style deltas, dual-arm DPE scenarios, experiment verdicts, committee votes, counterfactual analysis, decision replay) — but **no single module** performs evidence-based conflict resolution, scenario ranking, counterfactual simulation, and historical similarity comparison as one connected engine tied to PDE and structural governance.

Partial wiring exists inside `tae_paper_decision_engine.py` and the 19-step governance cycle. Large subsystems (counterfactual demos, strategic committee stack, historical pattern search) remain **outside** the PAPER cycle or feed PDE only as optional score biases.

---

## Executive Summary (10 Questions)

| # | Question | Answer | Primary modules | Connected to PDE / governance? |
|---|----------|--------|-----------------|-------------------------------|
| 1 | Conflict resolver? | **Partial — no unified resolver** | PDE `score_actions_for_ticker`, `strategic_conflict_detector.py`, `research_core/systemic_integration`, PDE hard-rule overrides | PDE: **yes** (inline). Strategic conflict: **no** |
| 2 | Scenario generation? | **Partial — philosophy / DPE dual-arm only** | DPE competitive/collaborative, `tae_market_philosophy_lab.py`, `research_core/entry_analysis/counterfactual_entry.py` | DPE: **yes** (step 16). Entry CF scenarios: **no** |
| 3 | Counterfactual simulation? | **Yes — fragmented, mostly unwired** | `research_core/entry_analysis`, `research_core/exit_analysis`, `tae_counterfactual_runtime.py`, `tae_decision_replay_composer.py`, `tae_paper_execution.py` | PAPER execution: **yes**. Entry/exit CF: **no** (demo/analysis) |
| 4 | Expected value scoring? | **Yes — heuristic, not probabilistic EV** | PDE `estimate_deltas`, `tae_paper_experiment_runner.py`, LTP bridge hypothesis scoring | PDE + experiments: **yes** |
| 5 | Historical similarity / replay? | **Partial — multiple formats** | `research/historical_patterns.py`, `decision_replay_engine.py`, `tae_decision_replay_composer.py`, longitudinal memory | Replay composer → PDE bias: **optional**. SPY similarity: **no** |
| 6 | Committee voting / arbitration? | **Yes — multiple stacks, domain-split** | `tae_profit_decision_committee.py`, `weighted_committee_decision.py`, `research_core/committee_runtime/`, `tae_investment_council.py` | Profit committee: **shadow only**. Investment Council: **synthesis report only** |
| 7 | Rank by profit/risk/capital efficiency? | **Yes — per-domain, not unified** | PDE action scores, DPE evaluator weighted metrics, LTP `priority_score`, Investment Council confidence sort | PDE + DPE: **yes**. Cross-ticker capital ranker: **no** |
| 8 | Connected to PDE / structural governance? | **Partial** | 19-step `tae_structural_governance.py`, PDE consumption graph | Hard rules + PDE + DPE + council report: **yes**. CF + strategic committee + similarity: **no** |
| 9 | Minimal wiring if building “new” layer? | **Thin orchestrator, not greenfield** | See §9 below | — |
| 10 | Would a “new” layer duplicate? | **Mostly yes if reimplemented** | PDE scoring, DPE evaluator, Investment Council, experiment runner already overlap | Extend/wire; do not rebuild |

---

## 1. Do we already have a conflict resolver?

**Answer: Partial — implicit resolver inside PDE; no dedicated conflict-resolution module.**

### What exists

| Module | Role | Conflict mechanism |
|--------|------|-------------------|
| `tae_paper_decision_engine.py` | Primary PAPER decision engine | Accumulates per-action scores from GII, PPG, shadow, signals, policy, experiments, knowledge, DPE bias, adaptive weights; `max(scores)` wins; hard overrides for `-3%` stop, position discipline, loss discipline |
| `strategic_conflict_detector.py` | Live signal vs regional allocation gap | Detects `SHORT_TERM_BUY_VS_STRATEGIC_DECREASE`, `WEAK_SIGNAL_VS_STRATEGIC_INCREASE`; writes `strategic_conflict_summary.txt` |
| `research_core/systemic_integration/interconnection_report.py` | Systemic conflict warnings | `ConflictWarning` list with risk levels |
| `research_core/score_decomposition/score_decomposition_report.py` | Signal evidence decomposition | `Conflict_Evidence_Score` component in cohort analysis |
| `tae_knowledge_base.py` | Learning conflict ingestion | Stores `conflict_warnings` from upstream reports |
| `tae_profit_decision_committee.py` | Per-ticker protection committee | Multi-source `votes` → weighted score → `final_committee_recommendation` (SHADOW_ONLY) |

### Grep result

No matches for `conflict_resolver`, `ConflictResolver`, `scenario_engine`, or `ScenarioEngine` in `*.py`.

### PDE inline conflict example

PDE explicitly resolves SELL vs PROTECT when weak lifecycle meets loss:

```1432:1435:tae_paper_decision_engine.py
            if current_pct <= -5.0:
                scores["SELL_PAPER"] += 15.0
                scores["PROTECT_PAPER"] = max(0.0, scores.get("PROTECT_PAPER", 0.0) - 15.0)
                evidence.append(f"weak lifecycle + {current_pct:.1f}% loss favors SELL over PROTECT")
```

Hard risk discipline short-circuits all scoring:

```1364:1384:tae_paper_decision_engine.py
    hard_risk_discipline = enforce_hard_risk_discipline(ticker, scores, evidence, ctx)
    if hard_risk_discipline.get("override"):
        ...
        return (
            "SELL_PAPER",
            scores,
            ...
        )
```

### Gap

- No cross-module resolver that ingests strategic conflicts, committee votes, DPE scenarios, and replay evidence into one arbitration record per ticker.
- `strategic_conflict_detector.py` is not consumed by PDE or structural governance.

---

## 2. Do we already have scenario generation?

**Answer: Partial — dual philosophy / DPE arms and research entry scenarios; no general PDE scenario engine.**

| Module | Scenario type | In PAPER cycle? |
|--------|---------------|-----------------|
| `tae_execution_splitter.py` + DPE executors | COMPETITIVE vs COLLABORATIVE paper portfolios from same decision events | Yes (step 16) |
| `tae_market_philosophy_lab.py` | Two philosophy models on same portfolio state | No (upstream intel; PDE reads `preferred_philosophy` via DPE adaptive) |
| `research_core/entry_analysis/counterfactual_entry.py` | Multiple entry filter/sizing scenarios with `best_scenario_id` / `worst_scenario_id` | No (analysis/demo) |
| `research_core/strategy_simulation/strategy_simulation_lab.py` | Baseline BUY vs alt filters | No |
| `tae_paper_experiment_runner.py` | Hypothesis arms (lifecycle hold/trim, protection, rotation, DPE philosophy) | Yes (learning step) |

PDE itself emits **one action per ticker**, not a ranked scenario set. Scenario multiplicity lives in DPE (2 arms) and experiment hypotheses (N arms), not in a shared scenario registry.

---

## 3. Do we already have counterfactual simulation?

**Answer: Yes — substantial code, mostly disconnected from governance.**

Prior audit (`TAE_COUNTERFACTUAL_EXECUTION_AUDIT.md`, 2026-07-07) verdict: **EXISTING_MODULES_NEED_WIRING**.

| Module | Counterfactual scope | Connected? |
|--------|---------------------|------------|
| `research_core/entry_analysis/counterfactual_entry.py` | Alt entry timing/filters on closed trades | Demo / analysis only |
| `research_core/exit_analysis/counterfactual_exit.py` | Alt exit timing | Demo / analysis only |
| `research_core/counterfactual_runtime/counterfactual_runner.py` | Orchestrates entry/exit demo scripts | Legacy wrapper |
| `tae_decision_replay_composer.py` | Shadow failure-mode consolidation (protect/cooldown/registry) | Consumed by PDE as score bias if artifact present; **not a step in structural governance** |
| `decision_replay_engine.py` | Registry WIN/LOSS win-rate by decision type | Legacy; not in cycle |
| `tae_paper_execution.py` | Forward PAPER fills from PDE decisions | Fully integrated (step 11) |
| `tae_profit_protection_validation.py` | Historical shadow protection vs HOLD | Upstream intel for PDE protection bias |

**Missing:** sell-all / liquidation scenario, historical canonical-state replay, unified canonical-vs-PAPER counterfactual PnL delta (partial data at step 17 report only).

---

## 4. Do we already have expected value scoring?

**Answer: Yes — heuristic expected deltas, not formal probability × payoff EV.**

### PDE (`estimate_deltas`)

Produces per-decision:

- `expected_profit_delta`
- `expected_risk_delta`
- `capital_efficiency_delta`

Sourced from experiment results when available, else rule-based heuristics from missed USD and action type (`tae_paper_decision_engine.py` ~L1190–1238).

### Experiment runner

`tae_paper_experiment_runner.py` scores hypotheses with:

- `expected_profit_delta_usd` / `expected_profit_delta_pct`
- `risk_delta`
- `capital_efficiency_delta`
- `hypothesis_profit_capture_rate`

Functions: `score_lifecycle_hold`, `score_lifecycle_trim`, `score_protection`, `score_rotation`, `score_dpe_philosophy`.

### DPE evaluator

`tae_dpe_result_evaluator.py` compares realized metrics between arms with weighted `overall_winner()` — outcome comparison, not forward EV.

### Gap

No module computes `EV = Σ P(outcome) × payoff` with calibrated probabilities. Confidence in PDE is `scores[best] / 100`, not aggregated evidence probability.

---

## 5. Do we already have historical similarity / replay?

**Answer: Partial — three different “replay” concepts coexist.**

| Module | Mechanism | PDE / cycle link |
|--------|-----------|------------------|
| `research/historical_patterns.py` | SPY feature-vector distance → top-N analog dates + forward returns | Standalone research script |
| `decision_replay_engine.py` | `decision_registry.csv` WIN/LOSS stats by decision label | Legacy |
| `tae_decision_replay_composer.py` | Failure modes, shadow recommendations, advisory readiness | PDE reads `tae_decision_replay.json` for named confidence rules |
| `tae_longitudinal_outcome_memory.py` | Decision lifecycle + adaptation hints | PDE consumes hints; governance step 13 |
| `research_core/market_intelligence/event_schema.py` | `context_similarity_score`, `event_similarity_score` fields | Schema only; not PDE input |

PDE consumption of replay:

```817:840:tae_paper_decision_engine.py
    replay_doc = ctx.get("decision_replay") or {}
    ...
    for rec in replay_doc.get("recommendations") or []:
        if _s(rec) == "DO_NOT_PROMOTE_TO_LIVE":
            rules_applied.extend(apply_named_rule(scores, "DO_NOT_PROMOTE_TO_LIVE"))
```

**Gap:** No ticker-level “find similar past decisions and rank actions by realized outcome” engine wired to PDE scoring.

---

## 6. Do we already have committee voting / arbitration?

**Answer: Yes — multiple committee stacks; none arbitrates PDE action conflicts directly.**

| Stack | Domain | Voting model | Overrides PDE? |
|-------|--------|--------------|--------------|
| `tae_profit_decision_committee.py` | Profit protection per ticker | `protection_rules_vote`, brain/memory votes → score band | No (SHADOW_ONLY) |
| `tae_profit_decision_governor.py` | Materialized view over profit committee | Ranks recommendations (`REC_RANK`, `CONTEXT_RANK`) | No |
| `weighted_committee_decision.py` | Macro/strategic BUY/WAIT/SELL | Weighted votes from `adaptive_weights.csv` | No; separate from PAPER |
| `research_core/committee_runtime/committee_runner.py` | Orchestrates 9+ committee scripts | Subprocess chain | No |
| `research/strategic_committee.py` | Regime + allocation text rules → AGGRESSIVE BUYING / WAIT | Rule table, not weighted evidence | No |
| `tae_investment_council.py` | Operator synthesis brief | Aggregates PDE, GII, DPE, governance — **no independent vote** | **Explicitly does not override hard rules** |
| `tae_decision_governor.py` | Advisory materialized view | Merges replay, committee, confidence | No (READ_ONLY advisory) |

Investment Council is **report-only synthesis** (rank-20 in governance), not an arbitration engine.

---

## 7. Do we already rank decisions by profit / risk / capital efficiency?

**Answer: Yes — per subsystem; no unified portfolio-level ranker.**

| Layer | Ranking key | Output |
|-------|-------------|--------|
| PDE | `score_actions_for_ticker` → best action; `risk_score`, `expected_profit_delta`, `confidence` | `paper_decisions.json` |
| DPE evaluator | Weighted metric wins (`total_pnl`, `max_drawdown`, `capital_efficiency`, …) | `evaluation.json` → `overall.winner` |
| LTP bridge | `priority_score` (e.g. missed_usd / 5), hypothesis confidence | `hypotheses.json`, experiment queue |
| Experiment runner | Verdicts: PROMISING / REJECT / CONTINUE_TESTING / NEEDS_MORE_DATA | `experiment_results.json` |
| Investment Council | Sort by `confidence` within action buckets | Council ranked lists |
| Rule survival | Win rate, net PnL → lifecycle state influence on PDE weights | `rule_lifecycle.json` |

**Gap:** No module ranks all tickers for **capital allocation** under a single profit/risk/efficiency objective (e.g. Kelly-style or constrained optimizer).

---

## 8. Are these connected to PDE / structural governance?

**Answer: Partially connected — core PAPER path yes; research/advisory path no.**

### Structural governance 19+1 steps (`tae_structural_governance.py`)

| Rank | Step | Relevant capability |
|------|------|---------------------|
| 4 | HARD RISK | `-3%` stop → PDE override |
| 5–9 | PDE layers | Inline conflict resolution + EV deltas |
| 10 | LEARNING / ADAPTIVE | LTP bridge artifacts |
| 11 | PAPER EXECUTION | Forward simulation |
| 13 | OUTCOME MEMORY | Longitudinal hints → PDE |
| 14 | RULE SURVIVAL | Rule lifecycle bias |
| 15 | ADAPTIVE WEIGHTS | Action weight caps → PDE |
| 16 | DPE | Dual-arm scenario comparison |
| 17 | CANONICAL VS PAPER | Outcome comparison report |
| 20 | INVESTMENT COUNCIL | Synthesis only |

### PDE upstream consumption graph (selected)

PDE loads and applies biases from:

- GII, PPG, APPE, shadow validation, knowledge base, confidence evolution
- `tae_decision_replay.json` (if present)
- DPE evaluator + adaptive (`preferred_philosophy`)
- Experiment results, adaptive paper weights, rule lifecycle, hard risk JSON

### Not in governance cycle

- `tae_decision_replay_composer.py` (artifact consumed if pre-generated; not orchestrated)
- `tae_market_philosophy_lab.py` (indirect via DPE adaptive)
- Counterfactual entry/exit demos
- `strategic_conflict_detector.py`, weighted committee stack
- `research/historical_patterns.py`

### `runtime_outputs/` snapshot (evidence of active DPE/LTP path)

Present artifacts include: `paper_decisions/`, `paper_execution/`, `dpe/paper_competitive|collaborative/`, `dpe/result_evaluator/`, `learning_to_profit/`, `longitudinal_memory/`, `adaptive_weights/`. No unified `conflict_resolution/` or `scenario_engine/` directory.

---

## 9. If not connected — minimal wiring needed

A **thin orchestrator** (not a new decision engine) would suffice:

1. **Pre-PDE refresh** — Run `tae_decision_replay_composer.py` and optionally counterfactual entry/exit on demand; register as governance sub-step or PDE prerequisite.
2. **Conflict record per ticker** — Emit JSON joining: PDE `action_scores`, strategic conflicts (if any), profit committee vote (shadow), DPE preferred arm, experiment verdict — **read-only view** consumed by Investment Council (extend council, don’t duplicate PDE).
3. **Scenario registry** — Normalize DPE arms + experiment hypotheses + entry CF `scenarios[]` into one schema; rank via existing DPE `overall_winner()` + experiment `PROMISING` verdicts.
4. **Execution ordering fix** — Filter or reorder `paper-execution` vs `paper-experiments` so PROMISING verdicts can gate execution (per counterfactual audit finding).
5. **Canonical comparator** — Promote step-17 report logic into a reusable diff module for counterfactual PnL questions.
6. **Hard-rule firewall** — Any new layer must remain REPORT_ONLY or bias-only; hard risk / reconciliation gates stay authoritative (Investment Council pattern).

**Do not build:** new per-ticker scorer, new committee voter, or new EV formula — extend existing PDE + DPE evaluator + experiment runner.

---

## 10. Is any proposed “new” layer actually duplicate?

| Proposed capability | Existing equivalent | Recommendation |
|--------------------|---------------------|----------------|
| Unified conflict resolver | PDE `score_actions_for_ticker` + hard disciplines | **Extend PDE evidence export**, don’t replace |
| Scenario engine | DPE dual-arm + experiment hypotheses + entry CF | **Registry/orchestrator** over existing outputs |
| Counterfactual simulator | `research_core/entry_analysis`, `exit_analysis`, PAPER execution | **Wire demos into cycle**; no new sim core |
| EV scorer | PDE `estimate_deltas`, experiment runner scores | **Calibrate/heuristic upgrade** only if needed |
| Historical analogy | `historical_patterns.py`, longitudinal memory | **Connect similarity output to PDE hints** |
| Investment council arbitration | `tae_investment_council.py` (synthesis) | **Already added** — keep REPORT_ONLY |
| Decision governor | `tae_decision_governor.py` | Advisory view — don’t duplicate |
| Rule survival / adaptive weights | `tae_rule_survival.py`, `tae_adaptive_paper_weights.py` | Already in cycle — consume, don’t rebuild |

---

## Module Inspection Notes (requested files)

| File | Finding |
|------|---------|
| `tae_paper_decision_engine.py` | **Core implicit conflict resolver** — multi-source action scoring, hard overrides, EV deltas, consumes replay/DPE/weights |
| `tae_paper_experiment_runner.py` | Hypothesis EV-style scoring + PROMISING/REJECT verdicts; triggers validation |
| `tae_dpe_result_evaluator.py` | Competitive vs collaborative weighted winner; feeds PDE `preferred_philosophy` |
| `tae_execution_splitter.py` | Routes decision events to dual DPE jobs — scenario fork, not resolution |
| `tae_learning_to_profit_bridge.py` | Ranks hypotheses into experiment queue from GII, ledger, replay, DPE |
| `tae_decision_replay_composer.py` | Shadow replay consolidation → failure modes + promotion caution |
| `decision_replay_engine.py` | Legacy registry win-rate summary |
| `tae_market_philosophy_lab.py` | Two-model philosophy comparison; referee inputs from existing SSOT |
| `tae_investment_council.py` | Synthesis brief; ranks by confidence; **does not arbitrate** |
| `tae_rule_survival.py` | Rule lifecycle states from attribution; PDE bias multipliers |
| `tae_adaptive_paper_weights.py` | Capped action weights from validation/experiments/attribution |
| `tae_structural_governance.py` | 19-step + Investment Council; no dedicated conflict/scenario step |
| `tae_profit_decision_governor.py` | Shadow profit committee view with REC_RANK |
| `tae_decision_governor.py` | Unified advisory materialized view (replay + committee + confidence) |
| `research/strategic_committee.py` | Simple regime rule table → text recommendation |
| `research_core/` | Counterfactual entry/exit, committee runtime, score decomposition, strategy simulation — **analysis islands** |

---

## Connection Diagram (current state)

```mermaid
flowchart TB
  subgraph governance [Structural Governance Cycle]
    HR[Hard Risk]
    PDE[PDE score_actions]
    EXEC[PAPER Execution]
    MEM[Outcome Memory]
    RS[Rule Survival]
    AW[Adaptive Weights]
    DPE[DPE Dual Arm]
    CMP[Canonical vs PAPER]
    IC[Investment Council]
    HR --> PDE --> EXEC --> MEM --> RS --> AW
    PDE --> DPE
    EXEC --> CMP
    DPE --> IC
    PDE --> IC
  end

  subgraph fragmented [Fragmented - Not in Cycle]
    SCD[strategic_conflict_detector]
    CF[entry/exit counterfactual]
    HP[historical_patterns]
    WC[weighted_committee]
    DRC[decision_replay_composer]
  end

  DRC -.->|optional JSON bias| PDE
  CF -.x PDE
  SCD -.x PDE
  HP -.x PDE
  WC -.x PDE
```

---

## Verdict Rationale

| Candidate verdict | Why not chosen |
|-------------------|----------------|
| `ALREADY_BUILT_AND_CONNECTED` | No unified conflict/scenario engine; counterfactual + strategic committee + similarity not in cycle |
| `BUILT_BUT_NOT_CONNECTED` | Too narrow — several capabilities are partial implementations, not complete unwired modules |
| `MISSING_CORE_COMPONENTS` | PDE scoring, DPE comparison, experiments, committees, replay composer already exist |
| **`EXISTS_AS_FRAGMENTED_COMPONENTS`** | **Best fit** — capabilities spread across PDE, DPE, LTP, committees, research_core; partial PDE wiring; no single orchestrated path |

---

## Recommended Next Step (audit only — not implemented)

Before greenfield development, implement a **read-only Conflict & Scenario Registry** that:

1. Reads existing artifacts only (PDE scores, DPE evaluation, experiments, replay, rule survival).
2. Writes one JSON + markdown report under `runtime_outputs/`.
3. Plugs into Investment Council as an additional source section.
4. Does **not** override PDE decisions or hard governance gates.

This satisfies operator questions without duplicating `tae_paper_decision_engine.py`, `tae_dpe_result_evaluator.py`, or `tae_investment_council.py`.

---

*End of audit — READ_ONLY, no code changes, no commit.*
