# TAE Development Protocol v1.1

**Trading AI Ecosystem — Official Project Governance & Constitution**

| Field | Value |
|-------|-------|
| Version | 1.1 |
| Status | Active |
| Safety mode | ANALYSIS_ONLY \| PAPER_ONLY \| NO_BROKER \| NO_EXECUTION |
| Scope | All future TAE research, integration, and runtime work |

---

## 1. Purpose

This protocol defines how all future Trading AI Ecosystem (TAE) work is **planned, implemented, verified, saved, and integrated**.

TAE is a read-only research and paper-validation organism. It exists to:

- Analyze portfolio and strategy behavior without executing trades
- Accumulate evidence from validated research modules
- Rank and track paper strategy candidates
- Gate promotion review without auto-implementing live changes
- Coordinate subsystems through canonical pipelines and orchestration

This document is the **single governance reference** for humans and AI assistants working on TAE. It does not replace code; it governs how code and reports are produced.

---

## 2. Core Rule

All work must follow this sequence:

```
Think → Design → Check Existing Modules → Codex Implementation → Verify → Save → Integrate → Monitor
```

| Step | Description |
|------|-------------|
| **Think** | Clarify goal, constraints, inputs, outputs, and what must *not* change |
| **Design** | Specify module name, phase ID, data flow, reports, and integration point |
| **Check Existing Modules** | Search inventory, interconnection map, and codebase for overlap before writing code |
| **Codex Implementation** | Implement only what is missing; reuse canonical modules |
| **Verify** | Run demo, py_compile, protected-file checks, and validate JSON/TXT outputs |
| **Save** | Persist reports; create git checkpoint when requested |
| **Integrate** | Wire into orchestrator/runtime only via approved integration points |
| **Monitor** | Observe runtime health, paper tracking, and integration backlog |

**No step may be skipped.** Implementation before design or inventory check is a protocol violation.

---

## 3. Roles

### 3.1 Human Owner

- Sets goals, priorities, and acceptance criteria
- Approves phase scope and promotion review decisions
- Owns live bot, portfolio, and strategy threshold policy
- Requests git commits and PRs explicitly
- Has final authority on any live strategy change (outside TAE scope)

### 3.2 ChatGPT Architect / Validator

- Translates owner intent into phased designs
- Enforces ANALYSIS_ONLY / PAPER_ONLY constraints
- Reviews Codex output for duplication, contradictions, and integration fit
- Validates reports, verdicts, and Definition of Done
- Does **not** bypass canonical modules or authorize live execution

### 3.3 Codex Implementer

- Implements approved designs in the repository
- Reuses existing modules and report patterns
- Runs demos and verification commands
- Produces JSON/TXT artifacts
- Does **not** modify live execution paths unless explicitly authorized by Human Owner outside this protocol

---

## 4. Mandatory Pre-Implementation Checklist

Before any new module or phase work begins, confirm:

- [ ] Phase ID and goal documented (e.g. Phase IX C3)
- [ ] Constraints listed: ANALYSIS_ONLY, PAPER_ONLY, NO_BROKER, NO_EXECUTION
- [ ] Protected files identified and confirmed untouched:
  - `live_bot.py`
  - `dashboard_v2.py`
  - `config/settings.py`
  - `portfolio.csv`
  - `core/trades.py`
  - `core/portfolio_prices.py`
- [ ] Existing modules searched (`research_core/`, `integration_layer/`, inventory audit)
- [ ] Canonical module for this responsibility identified or proposed
- [ ] Inputs (JSON/CSV paths) and outputs (JSON/TXT paths) defined
- [ ] No competing runner or duplicate report name
- [ ] Demo script path defined (`tae_phase{N}_*_demo.py`)
- [ ] Expected final verdict string defined
- [ ] Integration point identified (or explicitly marked standalone)

---

## 5. Anti-Duplication Rule

**Do not build what already exists.**

Before creating a new module:

1. Read `tae_ecosystem_inventory_audit.json` and `tae_systemic_interconnection_map.json`
2. Check duplicate groups (accounting, evidence, simulation/ranking, evolution generations)
3. Prefer **extending readers**, **summaries**, or **orchestrator steps** over new pipelines

| If overlap exists… | Action |
|--------------------|--------|
| Same responsibility as canonical module | Mark new code VIEW_ONLY or do not build |
| Phase V vs Phase VIII evolution | Phase VIII `strategy_evolution/` is active; Phase V is LEGACY_PLANNING_ONLY |
| Individual ranking/validation steps | Use `daily_runner.py`; do not invoke steps directly |
| Multiple daily runners | Use `ecosystem_orchestrator.py` as entry point only |

Creating a competing runner is **forbidden** (see Section 13).

---

## 6. Single Source of Truth Rule

Each responsibility has exactly one canonical module:

| Responsibility | Canonical module |
|----------------|------------------|
| Accounting source of truth | `research_core/accounting/independent_double_entry.py` |
| Evidence source of truth | `research_core/evidence_engine/evidence_registry.py` |
| Strategy evolution pipeline | `research_core/strategy_evolution/daily_runner.py` |
| Integration approval | `integration_layer/evidence_gate.py` |
| Ecosystem daily entry point | `research_core/orchestrator/ecosystem_orchestrator.py` |
| Runtime state & health | `research_core/runtime/workflow_engine.py` |
| Systemic interconnection map | `research_core/systemic_integration/module_interconnection.py` |

**Precedence rules:**

- Evidence Engine > isolated Phase VII JSON reports
- Strategy Evolution Daily Runner > individual ranking/validation modules
- Ecosystem Orchestrator > manual multi-step demo execution
- Runtime foundation reads canonical JSON; it does not override them

Report stores (`*_report.py`) are **serializers only**, not sources of truth.

---

## 7. Validation Requirements

Every phase deliverable must include:

1. **Demo script** — runs module read-only, checks protected files (mtime)
2. **JSON report** — schema name, version, verdict, generated_at, safety_mode
3. **TXT report** — human-readable mirror of JSON
4. **Final verdict** — explicit enum string (e.g. `RUNTIME_FOUNDATION_READY`)
5. **py_compile** — all new/modified Python files compile cleanly

### Standard verification commands

```bash
python3 -m py_compile <new_or_modified_files>.py
python3 tae_phase{N}_<module>_demo.py
```

### Protected-file confirmation

Demos must snapshot mtimes of protected paths before and after execution and report `Protected files unchanged: True`.

### Health consistency (runtime work)

If health is DEGRADED, `issues` count must match documented degradation reasons (see Runtime C2.1). Missing connections are integration backlog issues, not silent degradation.

---

## 8. Git Checkpoint Requirements

- **Do not commit** unless Human Owner explicitly requests
- When committing:
  - Run `git status`, `git diff`, `git log` first
  - Never commit secrets (`.env`, credentials)
  - Never commit unintended changes to protected live files
  - Use clear commit messages focused on *why*
  - Do not force-push to main/master
- Prefer one logical phase per commit when possible
- Generated `tae_*.json` / `tae_*.txt` may be committed when they are phase deliverables

---

## 9. Integration Requirements

New modules must integrate through approved paths:

### Daily ecosystem flow (canonical)

```
Ecosystem Inventory Audit (periodic)
  → Evidence Engine refresh
  → Evidence Integration Gate
  → Strategy Evolution Daily Runner
  → Ecosystem Orchestrator (daily entry point)
  → Runtime Foundation (state, health, learning memory)
```

### Integration rules

- Wire new analyzers as **Evidence Engine inputs**, not parallel truth sources
- Add orchestrator steps only when Human Owner approves; do not fork orchestrator
- Update `tae_systemic_interconnection_map.json` after structural changes
- Document missing connections in inventory audit; runtime treats them as integration backlog
- Integration Gate runs **after** Evidence Engine, **before** live consideration (paper only)

### Do-not-rewrite list (canonical modules)

- `live_bot.py`, `dashboard_v2.py`, `config/settings.py`, `portfolio.csv`
- `core/trades.py`, `core/portfolio_prices.py`, `core/portfolio.py`
- `core/entry_filter.py`, `core/exit_intelligence.py`, `core/risk.py`, `core/allocation.py`
- `research_core/strategy_evolution/daily_runner.py`
- `research_core/evidence_engine/evidence_registry.py`
- `research_core/accounting/independent_double_entry.py`
- `integration_layer/evidence_gate.py`

Changes to these require explicit Human Owner approval and a separate change protocol outside TAE research phases.

---

## 10. Broker Readiness Rule

TAE operates with **NO_BROKER | NO_EXECUTION** by default.

- No module may place orders, call broker APIs, or emit BUY/SELL instructions
- `broker_readiness` in runtime state is a **placeholder** until a future gated phase explicitly defines broker integration (not in v1.0 scope)
- Dashboard reconcile tools are read-only audits, not execution paths
- Any future broker work requires a new protocol version and Human Owner sign-off

---

## 11. Paper-Only Default Policy

All TAE modules default to:

```
ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
```

- Reports must include safety banner
- Strategy candidates remain paper until promotion gate + Human Owner review
- Promotion gate produces **review candidates**, not implementations
- Paper tracking counts trades toward sample thresholds; it does not execute trades
- Threshold changes to live strategy are **out of scope** for Codex unless explicitly authorized

---

## 12. Definition of Done

A phase is **Done** when all of the following are true:

| Criterion | Required |
|-----------|----------|
| Demo runs exit 0 | Yes |
| JSON + TXT outputs generated with correct schema | Yes |
| Final verdict matches spec | Yes |
| Protected files unchanged | Yes |
| No new competing runner | Yes |
| No modification to live_bot / portfolio.csv / thresholds | Yes |
| py_compile passes | Yes |
| Integration point documented (or N/A justified) | Yes |
| Inventory/interconnection updated if architecture changed | When applicable |
| Human Owner acceptance | Yes |

Partial completion uses explicit verdicts (e.g. `PARTIAL_FAILURE`, `DEGRADED_WITH_KNOWN_INTEGRATION_BACKLOG`), never silent success.

---

## 13. Forbidden Actions

The following are **never** permitted under TAE Development Protocol v1.0:

1. Modify `live_bot.py` without explicit Human Owner authorization outside this protocol
2. Modify `portfolio.csv` or strategy thresholds during research phases
3. Execute trades or emit BUY/SELL instructions
4. Create duplicate daily runners or competing orchestrators
5. Override canonical JSON reports from secondary modules
6. Rewrite canonical modules instead of extending via approved integration
7. Invoke individual strategy_evolution steps when `daily_runner.py` is available
8. Bypass Evidence Integration Gate for implementation candidates
9. Force-push to main/master
10. Commit secrets or credentials
11. Delete existing modules without Human Owner approval
12. Auto-promote paper candidates to live strategy

---

## 14. Future Module Acceptance Criteria

A new module is **accepted** into TAE only if:

### 14.1 Design acceptance

- Unique responsibility not covered by canonical module
- Or explicitly classified as VIEW_ONLY / REPORT_ONLY / LEGACY_PLANNING_ONLY
- Phase ID assigned and recorded

### 14.2 Implementation acceptance

- Lives under `research_core/`, `integration_layer/`, or approved `tools/` (read-only)
- Follows existing patterns: dataclass reports, `to_dict()`, `format_text()`, `*ReportStore`
- Demo with protected-file mtime check
- No imports from or side effects on live execution core

### 14.3 Integration acceptance

- Listed in ecosystem inventory on next audit
- Role assigned in systemic interconnection map
- If part of daily flow: added to orchestrator or runtime via approved step (not parallel path)
- Missing connections updated if new gaps discovered

### 14.4 Operational acceptance

- Runtime health remains coherent (issues match degradation reasons)
- Learning memory and paper tracking remain consistent
- No new CONFLICT_RISK without documented precedence rule

### 14.5 Rejection triggers

Automatic rejection if the module:

- Duplicates an existing canonical responsibility
- Produces conflicting recommendations without precedence
- Modifies live execution paths silently
- Lacks demo, verdict, or safety banner

---

## 15. Ecosystem Constitution

This section defines the **constitutional purpose** of the Trading AI Ecosystem (TAE).

TAE is not a single bot, script, or strategy. It is an organism designed to evolve under evidence, supervision, and mathematical discipline.

The ecosystem exists to:

- **Continuously learn** — from every trade outcome, counterfactual, simulation, and runtime observation
- **Continuously validate** — through statistical audit, paper validation, promotion gates, and health monitoring
- **Continuously improve** — by comparing candidates, ranking strategies, and retiring underperformers
- **Preserve mathematical evidence** — via canonical reports, Evidence Engine aggregation, and independent accounting verification
- **Preserve human strategic supervision** — no stage auto-promotes to live execution without Human Owner review
- **Become increasingly profitable through statistically validated evolution rather than assumptions** — intuition informs hypotheses; evidence and validation authorize action

This constitution supersedes ad-hoc workflows. When practice conflicts with this document, the document governs until Human Owner explicitly amends the protocol.

---

## 16. Decision Hierarchy

All strategic and implementation decisions must flow through the following hierarchy. **No stage may be skipped.**

```
Market Data
    ↓
Evidence Engine
    ↓
Simulation Lab
    ↓
Statistical Validation
    ↓
Strategy Evolution
    ↓
Runtime Intelligence
    ↓
Human Review
    ↓
Implementation Approval
    ↓
Paper Validation
    ↓
Broker Readiness
    ↓
Real Broker
```

| Stage | Role | Canonical reference |
|-------|------|---------------------|
| Market Data | Raw inputs (portfolio, prices, marks) | `portfolio.csv` (read-only in TAE) |
| Evidence Engine | Aggregated source of truth | `evidence_registry.py` |
| Simulation Lab | Strategy counterfactual comparison | `strategy_simulation_lab.py` |
| Statistical Validation | Significance, audits, cohort analysis | `statistical_validation/`, Phase VII analyzers |
| Strategy Evolution | Candidate registry, ranking, promotion gate | `daily_runner.py` |
| Runtime Intelligence | State, health, learning memory | `workflow_engine.py` |
| Human Review | Owner acceptance, promotion decisions | Human Owner |
| Implementation Approval | Integration gate allowlist | `evidence_gate.py` |
| Paper Validation | Parallel paper tracking, sample thresholds | `paper_tracking_log.py` |
| Broker Readiness | Future gated phase (not active in v1.1) | Placeholder only |
| Real Broker | Live execution (outside default TAE scope) | `live_bot.py` — Human Owner only |

Skipping a stage — for example, promoting a strategy from simulation directly to live without Evidence Engine alignment, statistical validation, or Human Review — is a **constitutional violation**.

---

## 17. Knowledge Evolution

The ecosystem learns permanently from:

- Successful trades
- Losing trades
- Missed opportunities
- Delayed entries
- Delayed exits
- Drawdowns
- Volatility
- Sector rotation
- Macro environment
- Historical simulations
- Paper strategies
- Runtime statistics

**Knowledge accumulates permanently.** Reports (`tae_*.json`), learning memory (`tae_runtime_learning_memory.json`), evidence items, and journal entries form a cumulative record. New phases must **append and integrate** knowledge; they must not discard validated history without documented reason and Human Owner approval.

Codex and ChatGPT Architect must treat prior evidence as binding context unless a new statistical audit explicitly supersedes it.

---

## 18. Continuous Improvement Rule

**No strategy is permanent.**

Every strategy remains a **candidate** until:

- it is **statistically outperformed** by another validated candidate, or
- it is **statistically invalidated** by evidence, validation, or promotion gate blockers

The ecosystem continuously compares every strategy against every other strategy through:

- Simulation Lab comparisons
- Parallel paper validation
- Continuous ranking engine
- Promotion gate and paper tracking thresholds

`LIVE_BASELINE` is the reference anchor, not an immutable optimum. Paper candidates that beat baseline on PnL, profit factor, and expectancy — with sufficient sample — advance toward promotion **review**, never automatic live replacement.

---

## 19. Journal Policy

The **official Trading AI Journal** records the narrative and historical arc of the ecosystem. It is distinct from JSON technical reports.

The journal records:

- Architecture decisions
- Implementation milestones
- Discoveries
- Failures
- Statistical breakthroughs
- Validation reports (summaries and interpretations)
- Ecosystem evolution

**The journal supports future technical documentation and the future book, but does not drive engineering decisions.**

Engineering decisions are driven by:

- This protocol (v1.1)
- Canonical JSON reports and verdicts
- Evidence Engine alignment
- Human Owner approval

Journal entries may inform context and communication; they may not override mathematical governance (Section 21) or skip the decision hierarchy (Section 16).

---

## 20. Architecture Review Process

Section 2 defines the core implementation sequence. **This section extends and formalizes it** for all non-trivial work. Implementation is **never** considered complete before architecture validation.

```
Think
    ↓
Architecture Design
    ↓
Architecture Review
    ↓
Check Existing Modules
    ↓
Codex Implementation
    ↓
Verification
    ↓
Architecture Validation
    ↓
Integration Review
    ↓
Commit
    ↓
Monitoring
```

| Step | Owner | Outcome |
|------|-------|---------|
| Think | Human Owner + Architect | Goal, constraints, non-goals |
| Architecture Design | Architect | Module boundaries, I/O, integration point |
| Architecture Review | Architect + Owner | Approved design before code |
| Check Existing Modules | Codex + inventory audit | Duplication check |
| Codex Implementation | Codex | Read-only code, demos, reports |
| Verification | Codex | py_compile, demo, protected files, verdict |
| Architecture Validation | Architect | As-built matches design; no scope creep |
| Integration Review | Architect | Orchestrator/runtime/interconnection fit |
| Commit | Codex (on Owner request) | Git checkpoint |
| Monitoring | Runtime + Owner | Health, paper tracking, backlog |

**Implementation is never considered complete before architecture validation.**

---

## 21. Mathematical Governance

The following principles are **non-negotiable** within TAE:

1. **Evidence always overrides intuition.** Hypotheses require evidence items or statistical audit support.
2. **Statistics override assumptions.** Sample size, significance, and cohort comparisons govern promotion eligibility.
3. **Validation overrides opinions.** Parallel paper validation and promotion gate blockers cannot be waived by narrative alone.
4. **Integration overrides isolated optimization.** A module that improves a local metric but breaks ecosystem coherence is rejected.
5. **Long-term ecosystem profitability has priority over short-term local improvements.** CLOSED_FREEZE distortions, legacy cohorts, and single-trade anecdotes do not override portfolio-level evidence.

When ChatGPT Architect and Codex Implementer disagree, **measured reports and verdicts** resolve the dispute — not preference or recency.

---

## Appendix A — Recommended Daily Operator Command

```bash
python3 tae_quick_health_check.py
```

Official read-only quick health check consolidating Phase IX runtime health, live-ops readiness signals, and ecosystem artifact status. Does not start/stop bot or broker.

For full ecosystem regeneration (optional, not required daily):

```bash
python3 tae_phase8_ecosystem_orchestrator_demo.py
python3 tae_phase9_runtime_foundation_demo.py
```

---

## Appendix B — Key Artifact Index

| Artifact | Purpose |
|----------|---------|
| `tae_ecosystem_inventory_audit.json` | Module inventory, duplicates, missing connections |
| `tae_systemic_interconnection_map.json` | Canonical map, roles, conflict warnings |
| `tae_ecosystem_orchestrator.json` | Daily ecosystem run summary |
| `tae_evidence_engine_report.json` | Evidence source of truth |
| `tae_strategy_evolution_daily_runner.json` | Strategy evolution pipeline summary |
| `tae_runtime_foundation.json` | Runtime state, health, workflow |
| `tae_runtime_learning_memory.json` | Persistent learning snapshot |
| `tae_quick_health_check.json` | Official daily quick health summary |

---

## Appendix C — Version History

| Version | Date | Summary |
|---------|------|---------|
| 1.1 | 2026-06-28 | Ecosystem constitution, decision hierarchy, knowledge evolution, architecture review process, mathematical governance |
| 1.0 | 2026-06-28 | Initial protocol: governance, canonical modules, validation, integration, paper-only default |

---

*TAE Development Protocol v1.1 — Documentation only. No runtime behavior change.*
