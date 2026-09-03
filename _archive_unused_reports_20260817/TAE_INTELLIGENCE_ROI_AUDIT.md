# TAE Intelligence ROI Audit

**Generated:** 2026-07-14  
**Mode:** READ ONLY — no code changes, no commits, no implementation  
**Prior audit:** `TAE_DECISION_INTELLIGENCE_CONSUMPTION_AUDIT.md` (~65% consumed / ~35% unused)  
**Machine-readable:** `tae_intelligence_roi_audit.json`  
**Final decision authority:** `tae_paper_decision_engine.py` (PDE)

---

## Final verdict

### `HIGH_VALUE_UNUSED_INTELLIGENCE_EXISTS`

TAE is **not** intelligence-poor. The architecture already produces substantial predictive and profit-scenario intelligence. Approximately **65%** is materially consumed by the final PDE decision path; however, **multiple existing producers already contain measurable unrealized edge** that is consumed only by reports, dashboards, DPE shadow arms, or next-cycle learning — not by the final BUY/HOLD/SELL/SKIP decision.

This is **not** a missing-brain problem. It is a **wiring and cycle-order ROI** problem on intelligence that already exists.

---

## Executive summary

| Dimension | Finding |
|-----------|---------|
| Intelligence materially consumed by PDE | **~65%** |
| Intelligence unused / indirect / lagged | **~35%** |
| Subsystems inventoried | **42** |
| High predictive value, low PDE wiring | **≥6** |
| Largest shadow unrealized signals | Profit-target adapter, decision-replay protection (+$5,051 vs hold shadow), opportunity ledger ($829.72 missed) |
| PAPER outcome-validation sample | **4 closed outcomes** post-integrity — limits outcome-grade proof, not existence proof |

**No implementation recommended in this audit.** This report ranks where existing intelligence would yield the highest ROI if wired better — without creating new intelligence.

---

## Phase 1 — Intelligence producer inventory

| # | Subsystem | Primary artifact(s) | Producer module |
|---|-----------|-------------------|-----------------|
| 1 | Growth Intelligence (GII) | `tae_growth_intelligence.json` | `tae_growth_intelligence.py` |
| 2 | Opportunity Ledger | `tae_opportunity_cost_ledger.json` | `tae_opportunity_cost_ledger.py` |
| 3 | Profit Growth Analytics | `tae_profit_growth_analytics.json` | `tae_profit_growth_analytics.py` |
| 4 | Historical Intelligence | `historical_intelligence.csv` | `tae_historical_runtime_refresh.py` |
| 5 | Multi-Horizon Backtest | `multi_horizon_backtest.csv` | `tae_historical_runtime_refresh.py` |
| 6 | Strategic Intelligence | `strategic_intelligence_summary.txt` | strategic_intelligence stack |
| 7 | Horizon Vote | `horizon_vote_summary.txt` | `strategic_intelligence/horizon_vote_engine.py` |
| 8 | Historical Refresh | `runtime_outputs/historical_runtime/runtime_state.json` | `tae_historical_runtime_refresh.py` |
| 9 | Cross Validation | `tae_cross_validation_report.json` | research / refresh chain |
| 10 | Knowledge Base | `tae_knowledge_base.json` | `tae_knowledge_base.py` |
| 11 | Knowledge Consumption | PDE `apply_knowledge_base_bias()` | consumed via KB JSON |
| 12 | Longitudinal Memory | `runtime_outputs/longitudinal_memory/*` | `tae_longitudinal_outcome_memory.py` |
| 13 | Outcome Memory | `decisions.jsonl`, `knowledge.json`, `memory_index.json` | same |
| 14 | Adaptation Hints | `adaptation_hints.json` | longitudinal memory |
| 15 | Rule Survival | `rule_lifecycle.json` | `tae_rule_survival.py` |
| 16 | Adaptive Weights | `paper_action_weights.json` | `tae_adaptive_paper_weights.py` |
| 17 | Rule Attribution | `rule_outcome_attribution.json` | `tae_paper_execution.py` |
| 18 | Investment Council | `runtime_outputs/investment_council/council.json` | `tae_investment_council.py` |
| 19 | Counterfactual Entry | `tae_entry_counterfactual.json` | `research_core/entry_analysis` |
| 20 | Counterfactual Exit | `tae_exit_counterfactual.json` | `research_core/exit_analysis` |
| 21 | Decision Replay | `tae_decision_replay.json` | `tae_decision_replay_composer.py` |
| 22 | Experiment Runner | `experiment_results.json` | `tae_paper_experiment_runner.py` |
| 23 | Learning-to-Profit Bridge | `hypotheses.json`, `paper_experiment_queue.jsonl` | `tae_learning_to_profit_bridge.py` |
| 24 | Profit Context Engine | `tae_profit_context_engine.json` | `tae_profit_context_engine.py` |
| 25 | Profit Protection Shadow | `tae_profit_protection_shadow.json` | `tae_profit_protection_shadow.py` |
| 26 | Profit Protection Validation | `tae_profit_protection_validation.json` | `tae_profit_protection_validation.py` |
| 27 | PPG | `tae_portfolio_profit_governor.json` | `tae_portfolio_profit_governor.py` |
| 28 | APPE | `tae_adaptive_profit_policy_engine.json` | `tae_adaptive_profit_policy_engine.py` |
| 29 | Conflict Resolution | `conflicts.json` | `tae_conflict_resolution.py` |
| 30 | Decision State | `active_decisions.json` | `tae_decision_state.py` |
| 31 | Market Philosophy Lab | DPE events / lab outputs | `tae_market_philosophy_lab.py` |
| 32 | DPE Competitive | `runtime_outputs/dpe/paper_competitive/*` | `tae_dpe_competitive_executor.py` |
| 33 | DPE Collaborative | `runtime_outputs/dpe/paper_collaborative/*` | `tae_dpe_collaborative_executor.py` |
| 34 | DPE Evaluation | `runtime_outputs/dpe/result_evaluator/evaluation.json` | `tae_dpe_result_evaluator.py` |
| 35 | DPE Learning | `runtime_outputs/dpe/learning/learning.json` | `tae_dpe_learning_engine.py` |
| 36 | Adaptive Selector | `runtime_outputs/dpe/adaptive/adaptive.json` | `tae_dpe_adaptive_selector.py` |
| 37 | Profit Target Adapter | `tae_profit_target_adapter.json` | `tae_profit_target_adapter.py` |
| 38 | Winner Lifecycle Profiler | `tae_winner_lifecycle_profiler.json` | lifecycle profiler chain |
| 39 | Confidence Evolution | `tae_confidence_evolution.json` | `tae_confidence_evolution.py` |
| 40 | Intraday Fade Intelligence | `tae_intraday_fade_intelligence.json` | `tae_intraday_fade_intelligence.py` |
| 41 | Hard Risk | `runtime_outputs/governance/hard_risk.json` | `hard_risk_guardian.py` |
| 42 | Live Signals | `live_signals.csv` | signal producers / enrichers |

**Additional predictive scores (not separate engines):** master intelligence score, session intelligence, position intelligence, profit intelligence brain, profit memory engine, profit decision governor/committee (legacy shadow stack).

---

## Phase 2 — Capability matrix (abbreviated)

| Subsystem | Produces info | Scores | Rankings | Confidence | Profit expectation | Opportunity cost | Counterfactuals | Regime | Learning |
|-----------|:-------------:|:------:|:--------:|:----------:|:------------------:|:----------------:|:---------------:|:------:|:--------:|
| GII | ✓ | ✓ | ✓ | ✓ | partial | via ledger | — | partial | — |
| Opportunity Ledger | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | ✓ | — |
| Historical / Multi-Horizon | ✓ | ✓ | — | ✓ | partial | — | — | ✓ | — |
| Knowledge Base | ✓ | ✓ | — | ✓ | — | — | — | — | — |
| Longitudinal / Outcome Memory | ✓ | partial | — | ✓ | partial | — | — | — | ✓ |
| Rule Survival | ✓ | ✓ | — | — | — | — | — | — | ✓ |
| Adaptive Weights | ✓ | ✓ | — | ✓ | partial | — | — | — | ✓ |
| Rule Attribution | ✓ | ✓ | — | ✓ | ✓ | — | — | — | ✓ |
| Investment Council | ✓ | ✓ | ✓ | ✓ | ✓ | partial | — | ✓ | — |
| Counterfactual Entry/Exit | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | — | — |
| Decision Replay | ✓ | — | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Experiment Runner | ✓ | ✓ | — | ✓ | ✓ | — | — | — | ✓ |
| Profit Context | ✓ | ✓ | — | ✓ | partial | — | — | ✓ | — |
| Profit Protection | ✓ | ✓ | — | ✓ | ✓ | ✓ | partial | — | — |
| PPG / APPE | ✓ | ✓ | ✓ | ✓ | ✓ | partial | — | ✓ | partial |
| Conflict Resolution | ✓ | ✓ | ✓ | ✓ | ✓ | — | partial | — | — |
| Decision State | ✓ | ✓ | — | ✓ | — | — | — | — | — |
| DPE stack | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Profit Target Adapter | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | — |
| Hard Risk | ✓ | — | — | ✓ | — | — | — | — | — |
| Live Signals | ✓ | ✓ | — | — | — | — | — | partial | — |

---

## Phase 3 — Consumption trace

| Consumption path | Subsystems |
|------------------|------------|
| **Consumed directly by PDE** | Hard Risk, Decision State, Conflict Resolution, GII, PPG, APPE, Shadow/Validation, KB, Confidence Evolution, Historical SSOT, Live Signals, Adaptive Weights (lag-1), Rule Survival (lag-1), Longitudinal knowledge, DPE eval summary, Experiments/hypotheses |
| **Consumed indirectly (upstream of PDE)** | Profit Context → GII/PPG/APPE; Opportunity Ledger → GII; Winner Lifecycle → GII; Profit Growth Analytics → GII |
| **Consumed only by reports** | Investment Council, Profit Target Adapter, Counterfactual Entry/Exit, full Decision Replay scenarios, Canonical vs PAPER, Promotion Lock |
| **Consumed only by dashboard** | Session intelligence, master intelligence score, position intelligence summaries, decision replay summary text |
| **Consumed only by DPE** | Market Philosophy Lab raw scores, competitive/collaborative arm portfolios |
| **Consumed nowhere (PDE path)** | Counterfactual JSON (direct), Profit Target Adapter (direct), Investment Council (direct), Pattern discovery content (boolean only), Profit Decision Governor legacy |
| **Consumed after decision** | Outcome Memory, Rule Attribution refresh, Adaptive Weights production, DPE chain, Longitudinal ingest |
| **Consumed only for learning** | DPE Learning history, Experiment Runner verdicts (partial same-cycle via hypothesis rules) |

**PDE call chain (final authority):**

```
build_context() → score_actions_for_ticker()
  → hard risk → GII/PPG/APPE/shadow → horizon → stale penalty
  → KB → confidence rules → longitudinal knowledge → DPE eval bias
  → learning evidence → adaptive weights → protection validation
  → rule lifecycle → conflict resolution → decision state gate → hypothesis rules
→ build_decision()
```

**Cycle-order lag:** Outcome memory, rule survival, adaptive weights, and DPE run **after** PDE in `tae_structural_governance.py` — same-run decisions cannot use freshly computed learning from the current cycle.

---

## Phase 4 — Predictive evidence (existing artifacts)

Evidence uses **existing artifacts only**. PAPER post-integrity window has **4 closed outcomes** — outcome-validation confidence is limited, but existence and directional predictive signals are still assessable.

| Subsystem | Winners identified? | Losers identified? | Timing / exits | Churn | Predictive grade | Evidence |
|-----------|--------------------|--------------------|----------------|---------|------------------|----------|
| **Hard Risk** | — | ✓ AMAT/MU/SIE.DE stops | ✓ forced sells | ✓ reduced re-loss | **HIGH** | Realized -$451; stops necessary |
| **Decision State** | — | — | — | ✓ blocked churn | **HIGH** | 6 same_action skips, 0 duplicate orders |
| **Conflict Resolution** | partial | partial | partial | ✓ | **HIGH** | EV bias ±38 pts in PDE |
| **GII** | ✓ AAPL/PG | ✗ MRK top growth but -$39 open | weak on losers | — | **MEDIUM** | Top growth list includes MRK (loser) and PG (winner) |
| **PPG** | partial | ✓ HIGH_RISK posture | — | conservative | **MEDIUM** | PORTFOLIO_HIGH_RISK drives SKIP |
| **APPE** | — | ✓ CAPITAL_PRESERVATION | — | — | **MEDIUM** | policy_skip 13/25 cycle |
| **Profit Protection** | shadow winners | — | replay +$5,051 vs hold | — | **MEDIUM** | `tae_decision_replay.json` shadow delta |
| **DPE Evaluator** | ✓ COLLABORATIVE | ✓ vs competitive | better DD | — | **HIGH** | PF 1.03 vs 0.38; total_pnl +8.46 vs -309.50 |
| **Adaptive Weights** | partial | ✓ BUY at floor 0.85 | — | — | **MEDIUM** | Evidence-driven; lag-1 |
| **Rule Attribution** | — | ✓ all 12 rules negative | — | — | **MEDIUM** | 4 executions tracked |
| **Opportunity Ledger** | missed winners | missed timing | ✓ | — | **MEDIUM** | $829.72 missed; top HSBA.L/MU/AMAT |
| **Confidence Evolution** | — | ✓ DO_NOT_PROMOTE | — | ✓ | **MEDIUM** | Named rules in every PDE decision |
| **KB / Longitudinal** | partial | partial | partial | partial | **MEDIUM** | Rules applied; hints confidence-only |
| **Historical / Multi-Horizon** | partial | ✓ stale penalty | horizon gate | — | **MEDIUM** | Stale marks block BUY |
| **Profit Target Adapter** | ✓ per-ticker targets | ✓ urgency modes | ✓ exit thresholds | — | **MEDIUM** (unwired) | PROTECT_PROFIT / TIGHTEN_TRAIL per ticker |
| **Counterfactual Entry** | scenarios exist | ✓ skip filters | — | — | **UNKNOWN** | Pre-integrity baseline; stale |
| **Counterfactual Exit** | — | — | ≈ optimal | — | **LOW** | `EXITS_APPROXIMATELY_OPTIMAL`; no price data |
| **Investment Council** | ✓ HD BUY | ranks MRK growth | — | — | **LOW** (unwired) | Synthesis only; diverges from PDE |
| **Decision Replay** | ✓ protection best | ✓ cooldown sim | ✓ | partial | **MEDIUM** (mostly unwired) | Only DO_NOT_PROMOTE/readiness in PDE |
| **Experiment Runner** | PROMISING | REJECT | — | — | **MEDIUM** | REJECT → SKIP via hypothesis rules |
| **Adaptation Hints** | — | ✓ BUY -0.5 bias | — | — | **LOW** (score-unwired) | Confidence nudge only |
| **Market Philosophy Lab** | — | — | — | — | **UNKNOWN** | Indirect via DPE adaptive only |
| **Intraday Fade** | — | — | — | — | **UNKNOWN** | Not in PDE consumption audit path |

---

## Phase 5 — ROI matrix (selected subsystems)

| Subsystem | Engineering cost invested | Decision influence today | Historical predictive value | Estimated unrealized value | Priority if wired better |
|-----------|:-------------------------:|:------------------------:|:---------------------------:|:--------------------------:|:------------------------:|
| Profit Target Adapter | HIGH (dedicated adapter) | **NONE** (PDE) | MEDIUM | **HIGH** — dynamic exit targets per ticker | **P0** |
| Decision Replay / Protection | HIGH | **LOW** (DO_NOT_PROMOTE only) | MEDIUM | **HIGH** — $5,051 shadow protection delta | **P0** |
| Opportunity Ledger | HIGH | INDIRECT (via GII) | MEDIUM | **HIGH** — $829.72 classified missed | **P0** |
| Counterfactual Entry | MEDIUM | **NONE** | UNKNOWN | **HIGH** potential BUY filter | **P1** |
| DPE arm metrics | VERY HIGH | **LOW** (winner string only) | HIGH | **MEDIUM-HIGH** — philosophy proof exists | **P1** |
| Adaptation Hints | MEDIUM | **LOW** (confidence only) | LOW-MEDIUM | **MEDIUM** — validated action biases | **P1** |
| Same-cycle learning lag | STRUCTURAL | MEDIUM (lag-1) | MEDIUM | **MEDIUM-HIGH** — latency not new intel | **P1** |
| GII / Lifecycle | HIGH | **HIGH** | MEDIUM | LOW — already core scorer | P3 |
| Hard Risk / Decision State / CR | HIGH | **HIGH** | HIGH | LOW — already connected | — |
| Investment Council | MEDIUM | **NONE** | LOW | LOW-MEDIUM — operator divergence signal | P2 |
| Counterfactual Exit | MEDIUM | **NONE** | LOW | LOW — exits ≈ optimal | P4 |
| Pattern Discovery | LOW | **MINIMAL** (+3 ROTATE) | UNKNOWN | LOW | P4 |

---

## Phase 6 — TOP 10 by potential profitability increase (no new intelligence)

| Rank | Subsystem | Why | Current gap | Estimated uplift | Risk if wired |
|:----:|-----------|-----|-------------|------------------|---------------|
| **1** | **Profit Target Adapter** | Per-ticker dynamic partial TP, trailing, urgency already computed | Not referenced by PDE held branch | $50–200+ on open losers (MRK/LLY/PM) | Low — uses existing protection logic |
| **2** | **Decision Replay protection scenarios** | `protection_delta_vs_hold_usd: 5051.12` shadow | Only readiness/DO_NOT_PROMOTE wired | High shadow exit improvement | Low — shadow-only path exists |
| **3** | **Opportunity Cost Ledger** | $829.72 missed with category/severity/ticker | Indirect via GII; no direct PDE missed-profit bias | Medium — better skip/BUY calibration | Medium — shadow classifications |
| **4** | **Counterfactual Entry** | Scenario rankings for BUY filters | `research_core` isolated from PDE/CR | Medium — avoid weak BUYs | Medium — pre-integrity data stale |
| **5** | **DPE arm-level metrics** | Collaborative proven superior on normalized capital | PDE reads winner label only (+5 PROTECT) | Medium — philosophy-aligned actions | Low — already 75% collaborative |
| **6** | **Adaptation Hints score path** | `BUY_PAPER: -0.5`, `HOLD: +0.333` validated biases | Applied to confidence only, not scores | Low–medium per action | Low |
| **7** | **Same-cycle feedback reorder** | Weights/lifecycle/DPE after PDE | One-cycle lag on learning | Medium — faster evidence application | Low — governance order only |
| **8** | **Market Philosophy Lab per-ticker** | Philosophy fit scores exist | Only aggregate `preferred_philosophy` | Unknown–medium | Low |
| **9** | **Investment Council divergence** | Council ranks MRK growth; PDE HOLD; validation REJECT | Report-only synthesis | Low — conflict detection | Low |
| **10** | **Rule Attribution → faster disable** | All 12 rules negative expectancy on executions | Feeds weights lag-1 only | Medium — suppress bad rules sooner | Low |

---

## Key diagnostic answers

1. **Does unused intelligence contain unrealized edge?** **YES** — profit-target adapter, replay protection scenarios, and opportunity ledger quantify it.
2. **Is the brain missing?** **NO** — PDE consumes the core stack; gaps are wiring and lag.
3. **Is more trading history required to know intelligence exists?** **NO** — scenario and shadow artifacts already encode edge hypotheses.
4. **Is more trading history required to promote wiring?** **YES** — only 4 PAPER closed outcomes post-integrity for outcome-grade promotion.
5. **Highest ROI without new engines?** Wire existing **profit targets + replay protection + opportunity missed-profit bias** into PDE held-position and CR EV paths.

---

## What is already well utilized (do not duplicate)

- Hard Risk → PDE override
- Decision State → churn gate
- Conflict Resolution → EV scoring
- GII + PPG + APPE + Shadow → dominant action selection
- Confidence Evolution → named rule penalties
- Historical SSOT → horizon + stale penalties
- DPE evaluator winner → philosophy bias (summary level)

---

## Integrity and constraints observed

| Rule | Status |
|------|--------|
| READ ONLY | ✓ Audit only |
| No code changes | ✓ |
| No commits | ✓ |
| No new modules/engines | ✓ |
| Profit Integrity | PASS (`PAPER_PROFIT_INTEGRITY_CLOSED`) |
| Reconciliation | PASS |
| promotion_lock | false |

---

## Verdict selection rationale

| Candidate verdict | Fit |
|-------------------|-----|
| `INTELLIGENCE_FULLY_UTILIZED` | **Rejected** — ~35% unused; multiple high-value producers unwired |
| `INTELLIGENCE_PARTIALLY_UTILIZED` | **True but insufficient** — describes consumption %, not unrealized edge |
| `HIGH_VALUE_UNUSED_INTELLIGENCE_EXISTS` | **Selected** — existing artifacts already encode measurable unrealized profit scenarios |

**Machine-readable companion:** `tae_intelligence_roi_audit.json`
