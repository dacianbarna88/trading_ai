# TAE Investment Council Existence Audit

**Generated:** 2026-07-08  
**Mode:** READ ONLY — no code changes, no commit  
**Scope:** All modules, reports, and CLI commands in the TAE ecosystem

---

## Definition

An **Investment Council** is a single decision-synthesis component that answers most of these daily operator questions:

| # | Question |
| ---: | --- |
| Q1 | What are today's best BUY opportunities? |
| Q2 | What are today's highest-risk positions? |
| Q3 | Which positions should be SOLD? |
| Q4 | Which rules are currently strongest? |
| Q5 | Which rules are currently weakest? |
| Q6 | Which philosophy is currently preferred? |
| Q7 | What is the current market regime? |
| Q8 | If rebuilding the portfolio today, what would be bought and sold? |
| Q9 | What is the expected portfolio impact? |
| Q10 | What is today's final recommendation? |

**Overlap scoring:** Each question a module materially answers (full or partial) counts toward overlap.  
`overlap % = (questions answered ÷ 10) × 100`, rounded to nearest 5%.

**Governance connection:** A module is **YES** if it is imported, called, or invoked as a CLI step inside `tae_structural_governance.run_structural_paper_cycle()` (directly or via subprocess). **INDIRECT** modules feed JSON consumed by governed modules but are not cycle steps. **NO** means outside the structural governance hierarchy.

---

## Search methodology

| Search axis | Result |
| --- | --- |
| Exact phrase `Investment Council` / `investment_council` | **0 hits** across `.py`, `.md`, `.json`, `.txt` |
| Related terms: `council`, `committee`, `governor`, `morning-audit`, `top_growth`, `philosophy`, `regime`, `recommendation` | **40+ candidate modules** |
| CLI commands (`tae_cli/dispatcher.py`) | **36 commands** reviewed |
| Structural governance registry (`TAE_STRUCTURAL_GOVERNANCE.md`) | **19-step hierarchy** — cycle safety, not investment synthesis |
| Prior audits | `TAE_EXISTING_DISCIPLINE_AUDIT.md` — "no single executable trading constitution" |

---

## Final verdict

### **EXISTS_AS_MULTIPLE_MODULES**

The TAE ecosystem **does not contain a module named "Investment Council"**, but it **does contain many partial implementations** under other names:

- **Profit Decision Committee** — shadow protect/exit per ticker (not BUY/SELL PAPER)
- **Strategic Committee** — regime + top opportunity + final recommendation (live/research domain)
- **Morning Operational Audit** — closest **operator brief** aggregating GII, PPG, APPE, DPE, protection
- **Paper Decision Engine** — authoritative PAPER BUY/SELL/ROTATE per ticker
- **Growth Intelligence (GII)** — top growth candidates + global verdict
- **Structural Governance** — cycle safety verdict (`READY_FOR_PAPER_DAY`), not investment advice

No single module answers more than **~60%** of council questions. Collectively, **~90%** of questions are answered somewhere — but fragmented across **20+ modules** with competing "final" outputs.

---

## Question coverage summary

| Question | Primary module(s) | Gap |
| --- | --- | --- |
| Q1 Best BUY | `tae_growth_intelligence.py`, `tae_paper_decision_engine.py` | No unified ranked BUY list in cycle; GII is not a governance step |
| Q2 Highest risk | `hard_risk_guardian.py`, `tae_portfolio_profit_governor.py`, PDE loss discipline | Risk split across hard (-3%), soft (-5%/-7%), shadow (profit_at_risk) |
| Q3 SELL | PDE `SELL_PAPER`, hard risk override | Shadow stack uses EXIT_PROTECT_SHADOW, not SELL |
| Q4 Strongest rules | `tae_rule_survival.py`, PDE rule lifecycle | No council-style "top 5 strongest" report |
| Q5 Weakest rules | `tae_rule_survival.py`, `tae_knowledge_base.py` | Same — lifecycle exists, council brief does not |
| Q6 Market regime | `regime_intelligence_engine.py`, APPE policy_state, strategic txt summaries | No single regime SSOT in PAPER cycle |
| Q7 Portfolio rebuild | PDE `ROTATE_PAPER`, `research/global_rebalance.py` | No "rebuild today" synthesis module |
| Q8 Expected impact | `tae_learning_to_profit_bridge.py`, `tae_paper_experiment_runner.py` | Hypothesis priority_score, not portfolio-level impact |
| Q9 Portfolio impact | PDE `expected_profit_delta` per ticker | No aggregated portfolio impact forecast |
| Q10 Final recommendation | **Many competing outputs** (see below) | No single authoritative daily investment brief |

**Competing "final recommendation" artifacts:**

| Output | Module | Meaning |
| --- | --- | --- |
| `READY_FOR_PAPER_DAY` | `tae_structural_governance.py` | Cycle safety — not buy/sell advice |
| Per-ticker `action` | `tae_paper_decision_engine.py` | PAPER decision (BUY/SELL/HOLD/…) |
| `global_verdict` | `tae_growth_intelligence.py` | Growth stack health |
| `portfolio_verdict` | `tae_portfolio_profit_governor.py` | Shadow portfolio risk posture |
| `final_verdict` | `tae_morning_operational_audit.py` | Operational health score |
| `Final Recommendation:` | `research/strategic_committee.py` | Live strategic BUY/WAIT/REDUCE |
| `final_decision` | `weighted_committee_decision.py` | Live committee BUY/SELL/WAIT |
| `final_shadow_recommendation` | `tae_profit_decision_governor.py` | Shadow protect posture per ticker |

---

## Module inventory

### Tier A — Closest to a unified council brief

| Module / file | Purpose | Inputs | Outputs | CLI | Governance | Overlap | Reusable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `tae_morning_operational_audit.py` | Consolidated morning brief: accounting, GII, protection, PPG, APPE, DPE, infra | `tae_accounting_snapshot.json`, GII, shadow, PPG, APPE, DPE JSON/JSONL, infra | stdout report (no persistent council artifact) | `morning-audit` | **NO** | **55%** (Q1, Q2, Q6 partial, Q10) | **YES** — best aggregation shell |
| `tae_structural_governance.py` | 19-step PAPER safety hierarchy + cycle verdict | PAPER portfolio, hard risk, PDE, DPE, rule survival, reconciliation | `structural_governance.json`, cycle summary, governance reports | `full-paper-cycle` | **SELF** | **35%** (Q2, Q3 via PDE, Q4, Q10 cycle-only) | **YES** — authority layer, not investment brief |
| `tae_paper_decision_engine.py` | Authoritative PAPER action scoring per ticker | GII, PPG, APPE, shadow, DPE, hard_risk, rule_lifecycle, knowledge, signals | `paper_decisions.json`, discipline reports | `paper-decisions` | **YES** (ranks 5–9) | **60%** (Q1–Q3, Q4 partial, Q5 partial, Q6 partial, Q7, Q8 partial, Q10 per-ticker) | **YES** — core decision authority |
| `tae_growth_intelligence.py` | Unified growth intelligence integrator | GA, ledger, lifecycle, memory, governors, APPE | `tae_growth_intelligence.json/.md` | `growth-intelligence` | **INDIRECT** (PDE reads JSON) | **45%** (Q1, Q2, Q7 partial, Q10 global_verdict) | **YES** |

### Tier B — Committee / governor stack (shadow profit domain)

| Module / file | Purpose | Inputs | Outputs | CLI | Governance | Overlap | Reusable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `tae_profit_decision_committee.py` | One explainable shadow recommendation per ticker (HOLD/OBSERVE/WATCH/EXIT_PROTECT) | shadow, PIB, memory, validation JSON | `tae_profit_decision_committee.json/.md` | via `protect` | **NO** (upstream shadow) | **30%** (Q2, Q3 partial, Q10 shadow) | **YES** — protect domain only |
| `tae_profit_committee_learning.py` | Weighted committee member accuracy learning | PDC JSON, validation outcomes | `tae_profit_committee_learning.json/.md` | via `protect` | **NO** | **15%** (Q4 partial — member weights) | **YES** |
| `tae_profit_decision_governor.py` | Materialized VIEW over profit protect pipeline | PDC, PCE, PPG, APPE, committee learning | `tae_profit_decision_governor.json/.md` | `protect`, `portfolio-protect` | **NO** (UPSTREAM_SHADOW) | **35%** (Q2, Q3 partial, Q10 per-ticker shadow) | **YES** |
| `tae_portfolio_profit_governor.py` | Portfolio-level profit verdict (HIGH_RISK, etc.) | PDG, APPE, accounting | `tae_portfolio_profit_governor.json/.md` | `portfolio-protect` | **NO** (UPSTREAM_SHADOW) | **25%** (Q2, Q6 partial, Q10 portfolio) | **YES** |
| `tae_adaptive_profit_policy_engine.py` | Portfolio policy state (HIGH_RISK, PRESERVATION) | PPG, committee learning, accounting | `tae_adaptive_profit_policy_engine.json/.md` | `policy` | **INDIRECT** (PDE + capital safety gate) | **20%** (Q2, Q6, Q10 policy) | **YES** |
| `tae_profit_protection_shadow.py` | Hypothetical profit protection sims | portfolio, GII, signals | `tae_profit_protection_shadow.json` | via `protect` | **INDIRECT** (PDE reads) | **20%** (Q2 profit_at_risk, Q3 partial) | **YES** |
| `tae_profit_intelligence_brain.py` | Multi-factor shadow recs + Profit Survival Probability | shadow, memory, validation | `tae_profit_intelligence_brain.json` | via `protect` | **NO** | **25%** (Q2 PSP urgency, Q3 partial) | **YES** |
| `tae_profit_context_engine.py` | Pullback vs decay context; reads regime summaries | regime txt, committee, PIB | `tae_profit_context_engine.json/.md` | via `protect` | **NO** | **20%** (Q2, Q6 partial, Q10 context) | **YES** |
| `tae_decision_governor.py` | Legacy advisory posture (ALLOWED/BLOCKED/WATCH) | KB, committee runtime, confidence | `tae_decision_governor.json/.md` | market-open pipeline | **NO** (LEGACY_SHADOW) | **15%** (Q4 partial, Q10 posture) | **PARTIAL** — legacy live path |

**`protect` CLI pipeline:** shadow → brain → memory → committee → committee_learning → context → PDG

### Tier C — PAPER execution / risk / rules

| Module / file | Purpose | Inputs | Outputs | CLI | Governance | Overlap | Reusable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `hard_risk_guardian.py` | Hard STOP -3% / CRITICAL -5% on PAPER portfolio | `paper_portfolio.json` | `runtime_outputs/governance/hard_risk.json` | *(called by governance)* | **YES** (rank 4) | **20%** (Q2, Q3 hard override) | **YES** |
| `tae_paper_execution.py` | PAPER trade execution + reconciliation | `paper_decisions.json`, MTM prices | `paper_portfolio.json`, trades JSONL | `paper-execution`, `paper-mark-to-market` | **YES** (ranks 11–12) | **15%** (Q3 executes, Q9 realized impact) | **YES** |
| `tae_rule_survival.py` | Rule lifecycle (NEW→DISABLED) from PAPER attribution | rule_outcome_attribution | `rule_lifecycle.json`, survival report | `strategy-survival` | **YES** (rank 14) | **20%** (Q4, Q5) | **YES** |
| `tae_adaptive_paper_weights.py` | Evidence-driven PDE action weights | attribution, experiments | `paper_action_weights.json` | `adaptive-weights` | **YES** (rank 15) | **10%** (Q4 indirect) | **YES** |
| `tae_knowledge_base.py` | Read-only knowledge consolidation VIEW | replay, confidence, experiments | `tae_knowledge_base.json` | market-open pipeline | **INDIRECT** (PDE reads) | **15%** (Q4, Q5 named rules) | **YES** |
| `tae_confidence_evolution.py` | Confidence evolution + final recommendation (shadow) | KB, replay, signals | `tae_confidence_evolution.json/.md` | market-open pipeline | **INDIRECT** (PDE reads) | **15%** (Q4 SCORE_DECAY, Q10 section) | **YES** |

### Tier D — Philosophy / DPE / learning

| Module / file | Purpose | Inputs | Outputs | CLI | Governance | Overlap | Reusable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `tae_dpe_adaptive_selector.py` | Adaptive philosophy recommendation | DPE learning, evaluator | `runtime_outputs/dpe/adaptive/adaptive.json` | `dpe-adaptive` | **YES** (rank 16) | **15%** (Q6 partial, Q10 DPE rec) | **YES** |
| `tae_market_philosophy_lab.py` | COMPETITIVE vs COLLABORATIVE model comparison | portfolio, GII, signals | `tae_market_philosophy_lab.json` | `philosophy` | **INDIRECT** (event bus) | **15%** (Q6, Q10 philosophy) | **YES** |
| `tae_dpe_result_evaluator.py` | Compare competitive vs collaborative PAPER results | DPE portfolios, metrics | `runtime_outputs/dpe/result_evaluator/evaluation.json` | `dpe-evaluator` | **YES** (rank 16) | **15%** (Q6 partial, Q8 metric deltas) | **YES** |
| `tae_learning_to_profit_bridge.py` | Ranked PAPER hypotheses + experiment queue | DPE, GII, confidence, replay | `hypotheses.json`, `paper_experiment_queue.jsonl` | `learning-profit` | **YES** (rank 10) | **20%** (Q1 hypotheses, Q8 priority_score) | **YES** |
| `tae_paper_experiment_runner.py` | Read-only hypothesis scoring experiments | hypotheses, decisions | `experiment_results.json`, validation | `paper-experiments` | **YES** (cycle step) | **15%** (Q8, Q10 validation verdict) | **YES** |
| `tae_longitudinal_outcome_memory.py` | PAPER decision lifecycle memory | decisions, trades, checkpoints | `longitudinal_memory/`, philosophy reports | `outcome-memory`, `philosophy-performance` | **YES** (rank 13) | **15%** (Q4 strategy survival, Q6 partial) | **YES** |

### Tier E — Live / strategic / legacy committees (separate domain)

| Module / file | Purpose | Inputs | Outputs | CLI | Governance | Overlap | Reusable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `research/strategic_committee.py` | Strategic committee: regime, risk, rotation, top opportunity | regime txt, `global_candidates.csv` | stdout / summary txt | *(standalone)* | **NO** | **40%** (Q1 top_opportunity, Q6, Q7 partial, Q10 Final Recommendation) | **PARTIAL** — live/research domain |
| `strategic_committee.py` | Adaptive strategic scoring from risk/conflict/rebalance txts | adaptive_risk, conflicts, rebalance summaries | `strategic_committee_summary.txt` | *(standalone)* | **NO** | **30%** (Q6, Q7, Q10) | **PARTIAL** |
| `strategic_intelligence/strategic_committee_engine.py` | Threshold/regional/sector/horizon vote aggregator | strategic intelligence inputs | committee summary txts | via committee runtime | **NO** | **20%** (Q6 votes) | **PARTIAL** |
| `weighted_committee_decision.py` | Weighted BUY/SELL/WAIT from adaptive_weights.csv | `adaptive_weights.csv` | `weighted_committee_decision.txt` | *(standalone)* | **NO** | **25%** (Q6 partial, Q10 final_decision) | **NO** — live CSV weights, forbidden path overlap |
| `tae_committee_runtime.py` | Legacy committee runtime orchestrator | committee module scripts | `tae_committee_runtime.json` | *(standalone)* | **NO** | **15%** (Q10 weighted_decision) | **NO** — live runtime, reads forbidden paths |
| `research_core/committee_runtime/committee_runner.py` | Invokes strategic/adaptive/weighted committee scripts | multiple committee scripts | various txt/csv artifacts | via `tae_committee_runtime.py` | **NO** | **25%** (Q6, Q10) | **NO** — live domain |
| `core/market_regime.py` | SPY SMA200 BULL/BEAR filter | SPY prices | regime enum | *(live_bot only)* | **NO** | **10%** (Q6 only) | **NO** — forbidden live path |
| `regime_intelligence_engine.py` | Regime profile from historical intelligence | historical_intelligence.csv | `regime_intelligence_summary.txt` | *(standalone)* | **NO** | **10%** (Q6) | **YES** — as upstream text |
| `research/global_rebalance.py` | Live CSV rebalance recommendations | portfolio.csv | `global_rebalance_recommendations.csv` | *(standalone)* | **NO** | **15%** (Q7 REDUCE list) | **NO** — live CSV |
| `strategic_rebalance_simulator.py` | Regional allocation alignment simulation | strategic inputs | `strategic_rebalance_simulation.json` | *(standalone)* | **NO** | **15%** (Q7, Q8 projected score) | **PARTIAL** |
| `tae_sprint4_research_council_report.py` | Research organism council demo | research organisms | `tae_sprint4_research_council_summary.txt` | *(demo)* | **NO** | **20%** (Q6, Q10 research decision) | **NO** — research-only |

### Tier F — Reports (generated, not modules)

| Report | Producer | Council overlap | Governance |
| --- | --- | --- | --- |
| `TAE_FULL_PAPER_CYCLE_REPORT.md` | `tae_full_paper_cycle.py` / governance | Q10 cycle verdict, top BUY/SELL/PROTECT highlights | **YES** |
| `TAE_STRUCTURAL_GOVERNANCE_REPORT.md` | `tae_structural_governance.py` | Step trace + hard rules + overrides | **YES** |
| `TAE_DECISION_DISCIPLINE_REPORT.md` | `tae_paper_decision_engine.py` | Q2–Q3 discipline, blocked no-position | **INDIRECT** |
| `TAE_RULE_SURVIVAL_REPORT.md` | `tae_rule_survival.py` | Q4–Q5 rule states | **YES** |
| `TAE_CANONICAL_VS_PAPER_REPORT.md` | canonical-vs-paper CLI | Q9 delta comparison (observed, not forecast) | **YES** (rank 17) |
| `TAE_ADAPTIVE_WEIGHTS_REPORT.md` | `tae_adaptive_paper_weights.py` | Q4 indirect | **YES** |
| `TAE_PHILOSOPHY_PERFORMANCE_REPORT.md` | longitudinal memory | Q6 partial | **INDIRECT** |
| `strategic_committee_summary.txt` | strategic committee engine | Q6, Q10 | **NO** |
| `weighted_committee_decision.txt` | weighted committee | Q10 BUY/SELL/WAIT | **NO** |

---

## CLI command map (investment-council relevance)

| CLI command | Primary module | Council role | Governance |
| --- | --- | --- | --- |
| `full-paper-cycle` | `tae_structural_governance.py` | Cycle authority + summary | **YES** |
| `morning-audit` | `tae_morning_operational_audit.py` | **Closest operator brief** | **NO** |
| `paper-decisions` | `tae_paper_decision_engine.py` | Per-ticker BUY/SELL authority | **YES** |
| `growth-intelligence` | `tae_growth_intelligence.py` | Top growth / global verdict | **INDIRECT** |
| `protect` | profit committee stack | Shadow protect/exit | **NO** |
| `portfolio-protect` | PPG + PDG | Portfolio risk posture | **NO** |
| `policy` | APPE | Policy state / regime proxy | **INDIRECT** |
| `philosophy` | philosophy lab | Philosophy comparison | **INDIRECT** |
| `dpe-adaptive` | DPE adaptive selector | Preferred philosophy | **YES** |
| `strategy-survival` | rule survival + longitudinal | Rule strength/weakness | **YES** (rule survival only) |
| `learning-profit` | LTP bridge | Hypothesis queue / expected mechanism | **YES** |
| `canonical-vs-paper` | comparison CLI | Observed portfolio delta | **YES** |
| `health` | quick health check | Infra readiness, not investment | **NO** |
| `opportunity` | opportunity cost ledger | Missed opportunities (inverse BUY) | **NO** |
| `winner` | winner lifecycle profiler | Lifecycle stage / decay risk | **NO** |
| `profit-targets` | profit target adapter | Numeric target guidance | **INDIRECT** |

---

## Structural governance vs Investment Council

`tae_structural_governance.py` answers: **"Is the PAPER ecosystem safe and coherent to operate today?"**

It does **not** answer: **"What should we buy and sell today for maximum risk-adjusted return?"**

| Capability | Structural governance | Investment Council (desired) |
| --- | --- | --- |
| Hard risk enforcement | **YES** | Needs synthesis into operator brief |
| Per-ticker PAPER actions | Via PDE (indirect) | Needs ranked daily list |
| Top BUY opportunities | **NO** (GII not in cycle) | **Required** |
| Strongest/weakest rules | Via rule_survival (indirect) | Needs council summary |
| Preferred philosophy | Via DPE (indirect) | Needs single SSOT |
| Market regime | **NO** | **Required** |
| Portfolio rebuild plan | **NO** | **Required** |
| Expected portfolio impact | **NO** | **Required** |
| Final investment recommendation | Cycle verdict only | **Required** |

---

## Name mapping — "Investment Council" equivalents

| Conceptual name | Actual TAE name(s) | Domain |
| --- | --- | --- |
| Investment Council | *(does not exist)* | — |
| Daily operator brief | **Morning Operational Audit** | Read-only aggregation |
| PAPER decision authority | **Paper Decision Engine** | PAPER_ONLY |
| Profit protection council | **Profit Decision Committee** | SHADOW_ONLY |
| Strategic investment committee | **Strategic Committee** (`research/strategic_committee.py`) | Live/research |
| Live weighted committee | **Weighted Committee Decision** | Live (`adaptive_weights.csv`) |
| Cycle safety council | **Structural Governance** | PAPER orchestration |
| Growth opportunity board | **Growth Intelligence (GII)** | Shadow integrator |
| Philosophy council | **DPE Adaptive Selector** + **Philosophy Lab** | PAPER learning |

---

## Gap analysis — what is missing for a true Investment Council

1. **No single orchestrator** that reads GII + PDE + hard_risk + rule_survival + DPE adaptive + regime and emits one daily brief.
2. **No ranked BUY list** in the governed cycle (GII runs outside governance).
3. **No portfolio rebuild synthesis** — ROTATE_PAPER (PDE) and global_rebalance (live) are disconnected.
4. **No aggregated expected impact** — only per-ticker PDE deltas and hypothesis priority scores.
5. **Competing final recommendations** — at least 8 artifacts claim "final" status with different meanings.
6. **Morning audit not in governance** — best aggregation layer is optional and stdout-only.
7. **Regime fragmented** — live `core/market_regime.py`, txt summaries, APPE policy_state, strategic intelligence — no PAPER SSOT.

---

## Reuse recommendation (informational only — no implementation)

If an Investment Council were built **without duplicating logic**, the highest-reuse composition would be:

| Layer | Reuse from |
| --- | --- |
| BUY ranking | GII `top_growth_candidates` + PDE `BUY_PAPER` scores |
| Risk ranking | `hard_risk.json` breaches + PPG portfolio_verdict + shadow profit_at_risk |
| SELL list | PDE `SELL_PAPER` + hard risk overrides |
| Rule strength | `rule_lifecycle.json` TRUSTED vs DISABLED + attribution JSON |
| Philosophy | DPE `adaptive.json` preferred_philosophy |
| Regime | regime txt summaries + APPE policy_state + strategic_intelligence_summary.txt |
| Rebuild | PDE `ROTATE_PAPER` decisions |
| Impact | LTP priority_score + PDE expected_profit_delta aggregation |
| Final rec | New synthesis above `morning-audit` breadth + `structural_governance` safety gate |

**Do not reuse directly:** `weighted_committee_decision.py`, `tae_committee_runtime.py`, `core/market_regime.py` (live/forbidden paths).

---

## Conclusion

| Criterion | Finding |
| --- | --- |
| Named "Investment Council"? | **NO** |
| Functionally equivalent single module? | **NO** |
| Partial coverage under other names? | **YES — extensive** |
| Connected to structural governance? | **Partially** — PDE, hard risk, rule survival, DPE yes; GII, morning audit, shadow committee stack no |
| Best existing candidate | `tae_morning_operational_audit.py` (operator brief) + `tae_paper_decision_engine.py` (PAPER authority) |

**Final verdict: EXISTS_AS_MULTIPLE_MODULES**

The Investment Council **does not exist as one module**, but **most of its capabilities already exist** as overlapping committees, governors, engines, and audits under different names — without a unified synthesis layer or single final investment recommendation.
