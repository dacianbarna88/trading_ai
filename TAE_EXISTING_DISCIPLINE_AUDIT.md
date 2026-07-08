# TAE Existing Discipline / Constitution Audit

**Generated:** 2026-07-08T15:30:00+00:00  
**Mode:** READ-ONLY — NO IMPLEMENTATION — NO CODE CHANGES  
**Scope:** Full-repo search for discipline, constitution, governance, risk gates, and enforcement modules

---

## Verdict

**PARTIALLY_DUPLICATED**

Core PAPER decision discipline, rule survival, execution guards, and accounting reconciliation **already exist and are connected** to `full-paper-cycle`. There is **no single executable “trading constitution” module**, and **PAPER -3% stop-loss enforcement is not connected** (live-only and standalone scripts exist under other names). Several shadow/advisory governors and live accounting auditors **duplicate intent** but run outside the daily PAPER cycle.

---

## Search concept → existing implementation

| Search term | Found as | Primary file(s) | Status |
| --- | --- | --- | --- |
| Trading constitution | Documentation only | `TAE_DEVELOPMENT_PROTOCOL.md`, `TAE_MASTER_GOVERNANCE_REPORT.md`, `TAE_GIT_GOVERNANCE.md` | **Doc-only, not executable** |
| Rule hierarchy | Named rule score deltas + lifecycle states | `tae_paper_decision_engine.py`, `tae_rule_survival.py` | **Active (PAPER)** |
| Hard rules | Named confidence rules, lifecycle DISABLED | `tae_paper_decision_engine.py` (`NAMED_RULE_SCORE_DELTAS`, `apply_rule_lifecycle_bias`) | **Active (PAPER scoring)** |
| Stop loss enforcement | **Live -3%** in bot; **PAPER -5%/-7%** in PDE; standalone guardian | `live_bot.py`, `tae_paper_decision_engine.py`, `hard_risk_guardian.py` | **Split / not unified** |
| Risk governor | Multiple shadow governors | `tae_decision_governor.py`, `tae_profit_decision_governor.py`, `tae_portfolio_profit_governor.py` | **Shadow, partially feeds PDE** |
| Execution discipline | PAPER execution guards | `tae_paper_execution.py` | **Active, connected** |
| Decision discipline | PDE position + loss discipline | `tae_paper_decision_engine.py`, `TAE_DECISION_DISCIPLINE_REPORT.md` | **Active, connected** |
| PAPER risk gate | APPE policy + PDE scoring gates | `tae_adaptive_profit_policy_engine.py` → consumed by PDE | **Active via JSON feed** |
| Hard risk gate | Standalone CSV scanner | `hard_risk_guardian.py` | **Built, NOT connected** |
| Governance framework | Master workflow docs + research_core governance | `TAE_MASTER_GOVERNANCE_REPORT.md`, `research_core/governance/*` | **Doc + shadow advisory** |
| Master workflow | 7-phase ladder documentation | `TAE_MASTER_GOVERNANCE_REPORT.md`, `TAE_DEVELOPMENT_PROTOCOL.md` | **Doc-only** |
| Risk constitution | Same as constitution docs | `TAE_DEVELOPMENT_PROTOCOL.md` § constitution | **Doc-only** |
| Trading rules | Knowledge base + named rules | `tae_knowledge_base.json`, PDE `NAMED_RULE_SCORE_DELTAS` | **Active (PAPER scoring)** |
| Stop-loss PAPER enforcement | Loss discipline (-5%/-7%), not -3% | `tae_paper_decision_engine.py` `enforce_loss_discipline()` | **Active, wrong threshold vs -3% ask** |
| Capital safety | APPE HIGH_RISK / PRESERVATION; capital base audit | `tae_adaptive_profit_policy_engine.py`, `tae_capital_base_integrity_audit.py` | **Partially connected** |
| Profit protection discipline | Shadow profit stack | `tae_profit_protection_shadow.json`, PPG/PDG/APPE chain | **Shadow → PDE input** |
| Rule survival | Rule lifecycle classifier | `tae_rule_survival.py`, `TAE_RULE_SURVIVAL_REPORT.md` | **Active, connected** |
| Policy gate | APPE policy_state; promotion gate | `tae_adaptive_profit_policy_engine.py`, `tae_full_paper_cycle.py` `build_promotion_gate()` | **Active (PAPER)** |
| Execution integrity | Live portfolio.csv SELL audit | `tae_portfolio_reconciliation.py`, `research_core/accounting/execution_integrity.py` | **Live/canonical, not PAPER cycle** |
| Accounting integrity | PAPER reconciliation + canonical audits | `tae_paper_execution.py`, `tae_capital_base_integrity_audit.py` | **PAPER active; canonical separate** |
| Reconciliation gate | PAPER portfolio formula checks | `tae_paper_execution.py` `validate_portfolio_reconciliation()`, wired in `tae_full_paper_cycle.py` | **Active, blocks cycle on FAIL** |

---

## Module inventory

### A. Connected to `full-paper-cycle` (ACTIVE)

| Module | What it enforces | Cycle connection | -3% stop | Blocks PROTECT/SELL w/o position | Blocks disabled rules | Blocks unreconciled accounting | Duplicate? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `tae_paper_decision_engine.py` | PAPER action scoring; position discipline; loss discipline (-5%/-7%); lifecycle bias; APPE HIGH_RISK BUY suppression; knowledge/confidence rules | `paper-decisions` step; pre-PDE loads rule lifecycle | **No** (-5%/-7% only) | **Yes** (score zero → SKIP) | **Yes** (DISABLED blocks positive deltas) | No | Core PDE — not duplicate |
| `tae_paper_execution.py` | Execution-only guards; SKIPPED_NO_POSITION; trade ledger; `validate_portfolio_reconciliation()` | `paper-execution`, `paper-mark-to-market`, `canonical-vs-paper` | No | **Yes** (`requires_position` → SKIPPED_NO_POSITION) | No (execution layer) | **Yes** (FAIL blocks cycle) | Core executor — not duplicate |
| `tae_rule_survival.py` | Rule lifecycle: NEW→DISABLED from attribution | Pre-PDE feedback + `strategy-survival` step | No | No | **Classifies** DISABLED; PDE applies bias | No | Runs twice per cycle (pre-PDE + strategy-survival) — **minor duplicate invocation** |
| `tae_full_paper_cycle.py` | Orchestration; forbidden diff; reconciliation FAIL block; broker flag; MTM all-stale block; promotion lock | Self | No | Indirect (via PDE + execution) | Indirect | **Yes** (`paper_reconciliation_ok`) | Orchestrator — not duplicate |
| `tae_live_promotion_lock.py` | `live_promotion_allowed=false`; forbidden PROMOTE_TO_LIVE wording | Post-cycle `promotion_lock` step | No | No | No | No | Active lock — not duplicate |
| `tae_paper_experiment_runner.py` | Decision validation verdicts (PROMISING/REJECT/NEEDS_MORE_DATA) | `paper-experiments` step | No | No | No | No | Validation layer — not duplicate |
| `tae_adaptive_paper_weights.py` | Action weight floors/ceilings from evidence | Pre-PDE + `adaptive-weights` step | No | No | Indirect (weight caution) | No | Active — not duplicate |
| `tae_longitudinal_outcome_memory.py` | Decision outcome memory / checkpoints | Pre-PDE + post-cycle | No | No | No | No | Active — not duplicate |
| `tae_adaptive_profit_policy_engine.py` | Portfolio policy_state (e.g. HIGH_RISK, CAPITAL_PRESERVATION_SHADOW) | **Indirect** — JSON consumed by PDE at decision time; upstream engines not in cycle | No | No | No | No | Shadow engine feeding PDE — **built, indirectly connected** |

### B. Built but NOT in `full-paper-cycle` (DISCONNECTED or SHADOW-ONLY)

| Module | What it enforces | Why disconnected | -3% stop | No-position block | Disabled rules | Reconciliation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `tae_decision_governor.py` | Advisory posture view (ALLOWED/BLOCKED/WATCH); merges protect/cooldown/knowledge | Not in `CYCLE_STEPS`; READ-ONLY advisory materialization | No | No | Partial (KB sanitize) | No | **Stale advisory stack** |
| `tae_profit_decision_governor.py` | Shadow profit protect recommendations | Not in cycle; feeds PPG/APPE upstream | No | No | No | No | **Shadow, upstream of PDE** |
| `tae_portfolio_profit_governor.py` | Portfolio verdict (PORTFOLIO_HIGH_RISK etc.) | Not in cycle directly; JSON read by PDE/APPE | No | No | No | No | **Shadow, upstream of PDE** |
| `hard_risk_guardian.py` | **-3% STOP_LIMIT, -5% CRITICAL** on open positions from `portfolio.csv` | Standalone script; not wired to CLI or cycle | **Yes (report only)** | No | No | No | **Built, NOT connected, live CSV only** |
| `tae_portfolio_reconciliation.py` | Live SELL row integrity vs `portfolio.csv` | Canonical/live audit; separate from PAPER portfolio | Audits -3% stop **reasons** in live sells | No | No | Live only | **Active for live, not PAPER cycle** |
| `research_core/accounting/execution_integrity.py` | Same as above (library) | Used by portfolio reconciliation | Audits live stop-loss sells | No | No | Live only | **Active for live** |
| `tae_capital_base_integrity_audit.py` | Capital base / deposits / contributed capital | Manual/audit command; not in daily cycle | No | No | No | Canonical accounting | **Built, not in cycle** |
| `tae_dpe_validation_start_gate.py` | 30-day validation readiness gate | Separate start-gate, not daily cycle | No | No | No | Partial (accounting delta check) | **Separate gate** |
| `research_core/governance/*` | Live advisory bridge, shadow attribution, daily intelligence | Live/shadow advisory path | No | No | No | No | **Parallel governance stack** |
| `research_core/strategy_evolution/promotion_gate.py` | Strategy candidate promotion (research) | Research pipeline, not PAPER daily cycle | No | No | No | No | **Separate domain** |
| `live_bot.py` | **STOP_LOSS_PCT = -3** live execution | Live path; explicitly forbidden from PAPER changes | **Yes (LIVE executes)** | N/A (live) | N/A | N/A | **Live-only, not PAPER** |

### C. Documentation-only “constitution” (NOT executable)

| Artifact | Content | Executable? |
| --- | --- | --- |
| `TAE_DEVELOPMENT_PROTOCOL.md` | Ecosystem constitution, decision hierarchy, mathematical governance | **No** |
| `TAE_MASTER_GOVERNANCE_REPORT.md` | 7-phase master workflow (Audit→Live) | **No** |
| `TAE_GIT_GOVERNANCE.md` | Git/version governance | **No** |
| `PROJECT_BOOK.md` § constitution | Session context reference | **No** |

---

## `full-paper-cycle` discipline wiring

```
historical_runtime_refresh
  → health (non-blocking exit)
  → morning-audit
  → learning-profit
  → [pre_pde_feedback]
       ├── longitudinal_memory
       ├── adaptive_paper_weights
       └── rule_survival          ← rule hierarchy / disabled rules
  → paper-decisions                ← decision discipline (position, loss, lifecycle, APPE policy)
  → paper-execution                ← execution discipline (no-position skip, ledger)
  → paper-mark-to-market           ← MTM + reconciliation refresh
  → paper-experiments              ← validation verdicts / policy gate input
  → outcome-memory / adaptive-weights / DPE chain
  → strategy-survival              ← rule_survival again (longitudinal + rules)
  → canonical-vs-paper
  → [collect_summary]
       ├── validate_portfolio_reconciliation  ← reconciliation gate (BLOCK on FAIL)
       ├── forbidden content diff           ← safety gate (BLOCK)
       ├── broker/live_money flags          ← safety gate (BLOCK)
       └── MTM ALL_STALE                    ← safety gate (BLOCK)
  → promotion_lock                 ← live promotion lock
```

**Connected discipline stack:** PDE → execution → MTM → reconciliation → cycle verdict.

**Not in cycle but consumed:** APPE/PPG/GII/shadow JSON (upstream artifacts must exist for PDE scoring).

---

## Eight enforcement questions (summary)

| Question | Answer |
| --- | --- |
| **1. Existing files/modules?** | Yes — see tables above. Closest “constitution” is doc-only; closest “hard rules” is PDE named rules + rule survival lifecycle. |
| **2. What each enforces?** | PDE: scoring discipline. Execution: position + accounting. Rule survival: rule demotion. Cycle: orchestration + hard blocks. Shadow governors: advisory/profit posture. Live bot/guardian: -3% on live CSV. |
| **3. Connected to full-paper-cycle?** | **PDE, execution, MTM, rule survival, reconciliation, promotion lock** — yes. **Decision/profit governors, hard_risk_guardian, live reconciliation, capital base audit** — no (or indirect JSON only). |
| **4. Enforces stop-loss -3%?** | **No on PAPER path.** PDE uses **-5% / -6% / -7%** thresholds. **-3% exists** in `live_bot.py` (live), `hard_risk_guardian.py` (standalone report on `portfolio.csv`), and live execution integrity audits — **none wired to PAPER cycle**. |
| **5. Blocks PROTECT/SELL without position?** | **Yes — dual layer:** PDE `enforce_position_discipline()` zeros scores → SKIP; execution `SKIPPED_NO_POSITION` if action somehow reaches executor. Verified in `TAE_DECISION_DISCIPLINE_REPORT.md`. |
| **6. Blocks disabled rules?** | **Yes — scoring layer:** `apply_rule_lifecycle_bias()` strips positive score influence for DISABLED rules; DEPRECATED/WATCHLIST reduced. Rule survival classifies; PDE enforces at decision time. |
| **7. Blocks unreconciled accounting?** | **Yes — PAPER only:** `validate_portfolio_reconciliation()` in execution/MTM; `full-paper-cycle` sets `BLOCKED_WITH_REASONS` on `paper_reconciliation_ok=false`. Live `portfolio.csv` reconciliation is separate and **not** a cycle blocker. |
| **8. Duplicate / stale / active?** | **Partially duplicated:** multiple shadow governors (decision/profit/portfolio), dual rule-survival invocation, three stop-loss thresholds (-3% live/guardian vs -5%/-7% PDE). **Active:** PDE + execution + rule survival + reconciliation. **Stale/disconnected:** `hard_risk_guardian.py`, standalone governors not in cycle, constitution docs without code. |

---

## Duplication map

| Area | Instances | Assessment |
| --- | --- | --- |
| Stop-loss threshold | `live_bot.py` -3%; `hard_risk_guardian.py` -3%/-5%; PDE -5%/-7% | **PARTIALLY_DUPLICATED — not unified** |
| Rule survival | Pre-PDE + `strategy-survival` step | **Minor duplicate run** (same module, twice per cycle) |
| Governors | `tae_decision_governor`, `tae_profit_decision_governor`, `tae_portfolio_profit_governor` | **Overlapping shadow advisory**; only JSON outputs feed PDE |
| Reconciliation | PAPER `validate_portfolio_reconciliation` vs live `execution_integrity` | **Different domains** (PAPER portfolio vs portfolio.csv) — not duplicate, parallel |
| Promotion gates | `full_paper_cycle` promotion_gate + `tae_live_promotion_lock` + `research_core/strategy_evolution/promotion_gate` | **Three gates, three purposes** (PAPER decisions, live lock, research strategies) |
| Constitution | Docs in 4+ markdown files | **No executable module** — documentation only |

---

## What is MISSING (relative to search list)

1. **Single executable “trading constitution” module** — only markdown governance exists.
2. **PAPER -3% hard stop enforcement wired to cycle** — PDE uses softer -5%/-7% scoring bias; `hard_risk_guardian.py` is disconnected and reads live CSV.
3. **Unified hard risk gate** — APPE HIGH_RISK is a scoring penalty, not a hard veto; no single `hard_risk_gate.py` in PAPER path.
4. **Master workflow as code** — 7-phase ladder is documentation, not a runtime gate beyond `full-paper-cycle`.
5. **Live execution integrity in PAPER cycle** — intentionally separate; live reconciliation does not block PAPER cycle.

---

## Recommendation (audit-only, no implementation)

Do **not** build a parallel constitution module without first mapping to:

- `tae_paper_decision_engine.py` (decision discipline + rule hierarchy)
- `tae_rule_survival.py` (rule lifecycle)
- `tae_paper_execution.py` (execution + reconciliation gate)
- `tae_full_paper_cycle.py` (orchestration + block conditions)

If a unified **-3% PAPER stop** is required, gap is real: existing -3% logic lives in **live/disconnected** modules, not the connected PAPER stack.

---

## Final verdict rationale

**PARTIALLY_DUPLICATED** because:

- **ALREADY_BUILT_AND_CONNECTED** for: decision discipline, execution discipline, rule survival, disabled-rule blocking, no-position blocking, PAPER reconciliation gate, promotion lock.
- **BUILT_BUT_NOT_CONNECTED** for: `hard_risk_guardian.py`, standalone governors, live execution integrity, capital base audit, constitution docs.
- **MISSING** for: single constitution module, PAPER -3% stop wired to cycle, unified hard risk gate.

No single verdict of ALREADY_BUILT_AND_CONNECTED (stop-loss and constitution gaps) or MISSING (core PAPER discipline exists) fits cleanly.
