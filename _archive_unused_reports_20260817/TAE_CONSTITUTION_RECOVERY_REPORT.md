# TAE Constitution Recovery Report

**Generated:** 2026-07-14T17:53:14+00:00
**Mode:** READ ONLY — no code changes, no commits

---

## B. Canonical verdict

```text
CANONICAL_TAE_CONSTITUTION_FOUND
```

**Canonical file:** `TAE_DEVELOPMENT_PROTOCOL.md`

No standalone `TAE_CONSTITUTION.md` or `CONSTITUTION.md` exists in the current tree or Git history. The repository explicitly labels `TAE_DEVELOPMENT_PROTOCOL.md` as **Constitution** in `PROJECT_BOOK.md`, `TAE_MASTER_CONTEXT.md`, and `TAE_MASTER_CONTEXT_AUDIT.md`.

---

## A. Files found

| Path | Git status | Introduced | Latest commit | Classification | Constitutional sections |
| --- | --- | --- | --- | --- | --- |
| `TAE_CONSTITUTION.md` | missing | — | — | missing | — |
| `CONSTITUTION.md` | missing | — | — | missing | — |
| `TAE_DEVELOPMENT_PROTOCOL.md` | tracked | b9be201314c1 | f6e55b0c5a09 | canonical | TAE Development Protocol v1.1, 1. Purpose, 2. Core Rule, 3. Roles, 4. Mandatory Pre-Implementation Checklist, 5. Anti-Duplication Rule (+19 more) |
| `TAE_GIT_GOVERNANCE.md` | tracked | d6277b5975fb | f6e55b0c5a09 | governance_companion | TAE Git Governance Standard v1.0, 1. Purpose, 2. Commit Categories, 3. Commit Rules, 4. Commit Message Standard, 5. Branch Rules (+6 more) |
| `PROJECT_BOOK.md` | tracked | 9eb8ffd7ec7e | 4cd669b80cd5 | operational_supplement | Trading AI — PROJECT BOOK (Canonical Journal), 1. Current Runtime Status, 2. Current TAE Architecture, 3. What Exists, 4. What Is Connected To LIVE, 5. What Is Report-Only (+10 more) |
| `SESSION_START.md` | tracked | 9eb8ffd7ec7e | 4cd669b80cd5 | operational_supplement | Session Start — Trading AI / TAE, Where we are, PAPER operator command (disciplined run), Current state (2026-07-14), What is already done (do not repeat), What we do NOT have (do not assume) (+9 more) |
| `TAE_MASTER_CONTEXT.md` | untracked | — | — | derived_or_historical | TAE Master Session Context (Generated), 1. Vision & strategic objective, 2. Canonical live spine (execution runtime), 3. Canonical TAE runtimes, 4. Architecture status, 5. Milestones (+4 more) |
| `TAE_MASTER_CONTEXT_AUDIT.md` | untracked | — | — | derived_or_historical | TAE Master Context Audit (Generated), Task 1 — Canonical documents, Task 2 — Canonical runtimes (summary), Task 3 — Architecture assessment, Task 4 — Master context generation, Task 5 — Quality check: canonical contradictions (+1 more) |
| `PROJECT_MAP.md` | tracked | 74b119cb0027 | f6e55b0c5a09 | derived_or_historical | Trading AI Project Map, Current Architecture, Core Daily Runner, Decision Registry & Outcome, Learning & Intelligence, Self-Learning Engines (+7 more) |
| `PROJECT_STATUS.md` | tracked | 74b119cb0027 | 5af317f238b1 | architecture_reference | Trading AI Project Status, TAE Ecosystem — Official Stable (Phase IX), Live Trading Stack — Current Stable Version, Current Stable Version, Latest Stable Snapshots, Active Core Systems (+8 more) |
| `TAE_STRUCTURAL_GOVERNANCE.md` | tracked | d53517ddc5fe | d53517ddc5fe | operational_supplement | TAE Structural Governance, Mandatory execution hierarchy, Rule classification, Hard rules enforced, Module registry, Outputs (+2 more) |
| `TAE_ARCHITECTURE.md` | tracked | 8aeff7af8759 | 8aeff7af8759 | architecture_reference | TAE Architecture, Overview, 1. Market Layer, 2. Organism Layer, 3. Organism Contract (Summary), 4. Knowledge Core (+6 more) |
| `TAE_MASTER_GOVERNANCE_REPORT.md` | tracked | 797ced820d42 | 797ced820d42 | governance_companion | TAE Master Governance Report, Executive verdict, Files created (this sprint), Workflow established, SSOT registry summary, Roadmap summary (+5 more) |
| `TAE_MASTER_DEVELOPMENT_WORKFLOW.md` | tracked | 797ced820d42 | 797ced820d42 | governance_companion | TAE Master Development Workflow, Purpose, Workflow overview, Phase 0 — Ecosystem Audit, Phase 1 — Architecture Design, Phase 2 — Shadow Build (+7 more) |
| `TAE_GOVERNANCE_RESET_SUMMARY.md` | tracked | 9eb8ffd7ec7e | 9eb8ffd7ec7e | governance_companion | TAE Governance Reset — Summary, Objective, Task 1 — Journal audit, Task 2 — PROJECT_BOOK.md, Task 3 — tae_checkpoint.sh, Task 4 — SESSION_START.md (+4 more) |
| `TAE_EXISTING_DISCIPLINE_AUDIT.md` | tracked | 09c13bb66d05 | 09c13bb66d05 | audit_inventory | TAE Existing Discipline / Constitution Audit, Verdict, Search concept → existing implementation, Module inventory, `full-paper-cycle` discipline wiring, Eight enforcement questions (summary) (+4 more) |
| `TAE_IMPLEMENTATION_ROADMAP.md` | tracked | f1e8f0e0c7fb | f1e8f0e0c7fb | governance_companion | TAE Implementation Roadmap — Connect Built Modules Safely, Executive Summary, Connection Rules (Non-Negotiable), Phase 1 — Already Connected (Maintain), Phase 2 — Safe to Connect Now, Phase 3 — Needs Shadow Validation First (+9 more) |

### Search results for requested filenames

| Requested | Result |
| --- | --- |
| `TAE_CONSTITUTION.md` | **Not found** (current or git history) |
| `CONSTITUTION.md` | **Not found** (current or git history) |

---

## D. Governance hierarchy

1. **TAE_DEVELOPMENT_PROTOCOL.md** — Constitution / single governance reference (v1.1)
2. **TAE_GIT_GOVERNANCE.md** — Git/version control companion to constitution
3. **PROJECT_BOOK.md** — Canonical project journal / runtime inventory SSOT
4. **SESSION_START.md** — Session operator bootstrap and daily commands
5. **TAE_STRUCTURAL_GOVERNANCE.md** — PAPER-only 19-step execution hierarchy (operational)
6. **tae_paper_decision_engine.py + tae_decision_state.py** — Main Decision Brain rules (PDE final authority per 2026-07-08 closure)
7. **TAE_MASTER_DEVELOPMENT_WORKFLOW.md / TAE_MASTER_GOVERNANCE_REPORT.md** — 7-phase sprint promotion ladder (process supplement)
8. **TAE_MASTER_CONTEXT.md** — Generated session bootstrap — explicitly NOT SSOT
9. **live_bot.py** — Live execution runtime — Human Owner authority for live changes

---

## E. Conflicts

### Authority order vs session docs

- **Constitutional / SSOT:** TAE_DEVELOPMENT_PROTOCOL.md §3.1 Human Owner has final authority on live strategy
- **Operational guidance:** TAE_MASTER_CONTEXT.md lists live_bot.py behavior first in authority order when in doubt
- **Assessment:** Operational bootstrap inverts emphasis; constitution governs per §15

### SESSION_START canonical doc list omits constitution file

- **Constitutional / SSOT:** PROJECT_BOOK.md §Reference index lists TAE_DEVELOPMENT_PROTOCOL.md as Constitution
- **Operational guidance:** SESSION_START.md Canonical docs (2026-07-08) lists STRUCTURAL_GOVERNANCE and brain closure audits but not TAE_DEVELOPMENT_PROTOCOL.md
- **Assessment:** Session bootstrap drift; constitution not cited in latest SESSION_START canonical list

### Stale generated context

- **Constitutional / SSOT:** TAE_MASTER_CONTEXT.md says regenerate after canonical doc updates; not SSOT
- **Operational guidance:** TAE_MASTER_CONTEXT.md still at 2026-07-05 X.Decision checkpoint; PROJECT_BOOK/SESSION_START at 2026-07-14 decision-risk sync
- **Assessment:** Derived doc stale vs journal; not a constitutional contradiction but operator hazard

### PAPER Main Decision Brain vs protocol default

- **Constitutional / SSOT:** Protocol v1.1 default ANALYSIS_ONLY | PAPER_ONLY | NO_EXECUTION; TAE is read-only research organism
- **Operational guidance:** 2026-07-08+ PAPER stack: PDE is MAIN DECISION BRAIN with paper execution via full-paper-cycle
- **Assessment:** Operational PAPER brain extends beyond original doc-only posture; not explicitly amended in protocol v1.1

### Hard risk -3% enforcement timing

- **Constitutional / SSOT:** TAE_STRUCTURAL_GOVERNANCE.md rank-4 HARD RISK -3%/-5%
- **Operational guidance:** TAE_EXISTING_DISCIPLINE_AUDIT.md (2026-07-08) noted hard_risk_guardian not connected; later structural governance commit wired PDE enforce_hard_risk_discipline
- **Assessment:** Audit predates structural governance wiring; current cycle implements -3% at PDE layer

### Governor live blocking

- **Constitutional / SSOT:** PROJECT_BOOK / MASTER_CONTEXT: governor live blocking NOT approved by design
- **Operational guidance:** X.8 RISK_ADVISORY blocks new BUY only on live path
- **Assessment:** Intentional partial live gate; consistent with Human Owner authority model

---

## Git commits containing constitutional material

- `b9be201 DOC: TAE Development Protocol v1.1`
- `d6277b5 DOC: TAE Git Governance Standard v1.0`
- `09c13bb TAE: Add canonical architecture and governance documents`
- `8aee600 TAE: Add Investment Council synthesis layer`
- `d53517d TAE: Structural governance consolidation of PAPER ecosystem`
- `7712886 TAE Governance: Make finish sprint command autonomous`
- `9eb8ffd TAE Governance: Add project book and checkpoint workflow`
- `dd30423 INTEGRATION: Governance daily intelligence migration`
- `1014b0f TAE Phase V A5: Governance daily intelligence checkpoint`

---

## C. Full constitutional text (canonical — verbatim)

Source: `TAE_DEVELOPMENT_PROTOCOL.md` — reproduced exactly as stored.

```markdown
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

**Stable release:** TAE V9.6 Stable (`b2bbd1e`) — Sprint IX.6; see `TAE_PROJECT_STATUS.md` and `archive/v9_6_stable/`.

---

*TAE Development Protocol v1.1 — Documentation only. No runtime behavior change.*
```

---

## Supplementary governing fragments (non-canonical — verbatim excerpts)

These documents contain governing principles but are classified as operational supplements, companions, or derived artifacts — not replacements for the constitution.

### `TAE_STRUCTURAL_GOVERNANCE.md` — PAPER 19-step hierarchy

```markdown
# TAE Structural Governance

**Mode:** PAPER_ONLY | NO_BROKER | NO_LIVE_PROMOTION  
**Authority:** `tae_structural_governance.py` — single orchestrator for the PAPER ecosystem.

## Mandatory execution hierarchy

Every PAPER cycle step runs in this order. Hard layers block downstream authority; policy and learning layers cannot override hard rules.

| Rank | Layer | Class | Module(s) |
| ---: | --- | --- | --- |
| 1 | DATA VALIDITY | HARD | `tae_historical_runtime_refresh.py` |
| 2 | ACCOUNTING RECONCILIATION | HARD | `tae_paper_execution.validate_portfolio_reconciliation()` |
| 3 | CAPITAL SAFETY | HARD | PAPER portfolio flags + APPE policy |
| 4 | HARD RISK RULES | HARD | `hard_risk_guardian.py` → `runtime_outputs/governance/hard_risk.json` |
| 5 | POSITION DISCIPLINE | HARD | `tae_paper_decision_engine.enforce_position_discipline()` |
| 6 | PROFIT PROTECTION | POLICY | PDE + shadow governors (upstream JSON) |
| 7 | LOSS CUTTING | POLICY | PDE `enforce_loss_discipline()` (-5%/-7% soft) |
| 8 | BUY ELIGIBILITY | POLICY | PDE buy scoring + capital hints |
| 9 | POLICY LAYER | POLICY | APPE / hypothesis rules |
| 10 | LEARNING / ADAPTIVE | LEARNING | `learning-profit` (pre-decision hypothesis queue) |
| 11 | PAPER EXECUTION | HARD | `tae_paper_execution.py` |
| 12 | MARK-TO-MARKET | HARD | `tae_paper_execution` MTM |
| 13 | OUTCOME MEMORY | LEARNING | `tae_longitudinal_outcome_memory.py` |
| 14 | RULE SURVIVAL | LEARNING | `tae_rule_survival.py` |
| 15 | ADAPTIVE WEIGHTS | LEARNING | `tae_adaptive_paper_weights.py` |
| 16 | DPE | LEARNING | `tae_dpe_*` chain |
| 17 | CANONICAL VS PAPER | REPORT_ONLY | canonical-vs-paper CLI |
| 18 | PROMOTION LOCK | HARD | `tae_live_promotion_lock.py` |
| 19 | FINAL VERDICT | HARD | `tae_structural_governance.compute_final_verdict()` |

## Rule classification

| Class | Meaning | Override authority |
| --- | --- | --- |
| **HARD** | Safety, accounting, position, execution, promotion | Blocks cycle; cannot be softened |
| **POLICY** | Profit protection, loss cutting, buy eligibility | Applied inside PDE after hard gates |
| **LEARNING** | Outcome memory, rule survival, adaptive weights, DPE | Influences scores; never bypasses HARD |
| **REPORT_ONLY** | Canonical vs PAPER, legacy audits | Observability only |
| **LEGACY** | Live CSV governors, shadow-only modules | Not in PAPER cycle authority |

## Hard rules enforced

1. **STOP_LOSS -3%** — `hard_risk_guardian` writes breach; PDE `enforce_hard_risk_discipline()` forces `SELL_PAPER` before soft logic.
2. **CRITICAL_LOSS -5%** — `FORCE_SELL_REQUIRED` at hard layer.
3. **No SELL/PROTECT/REDUCE/ROTATE without PAPER position** — PDE + execution `SKIPPED_NO_POSITION`.
4. **DISABLED rules** — rule lifecycle reduces influence; cannot boost scores.
5. **Unreconciled accounting** — reconciliation FAIL blocks final verdict.
6. **Stale critical data** — rank-1 gate FAIL blocks cycle.
7. **broker_executed / live_money** — capital safety FAIL.
8. **live_promotion_allowed=false** — promotion lock always enforced.
9. **Forbidden path diff = 0** — `live_bot.py`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt`, `core/`, `research_core/`.

## Module registry

| Module | Role | Cycle status |
| --- | --- | --- |
| `hard_risk_guardian.py` | HARD risk | ACTIVE (PAPER adapter) |
| `tae_paper_decision_engine.py` | HARD/POLICY decisions | ACTIVE |
| `tae_paper_execution.py` | HARD execution + reconciliation | ACTIVE |
| `tae_rule_survival.py` | LEARNING lifecycle | ACTIVE |
| `tae_adaptive_paper_weights.py` | LEARNING weights | ACTIVE |
| `tae_longitudinal_outcome_memory.py` | LEARNING memory | ACTIVE |
| `tae_live_promotion_lock.py` | HARD promotion block | ACTIVE |
| `tae_portfolio_profit_governor.py` | POLICY upstream | UPSTREAM_SHADOW |
| `tae_adaptive_profit_policy_engine.py` | POLICY upstream | UPSTREAM_SHADOW |
| `tae_profit_decision_governor.py` | POLICY upstream | UPSTREAM_SHADOW |
| `tae_profit_protection_validation.py` | POLICY upstream | UPSTREAM_SHADOW |
| `tae_decision_governor.py` | LEGACY advisory | LEGACY_SHADOW |
| `tae_portfolio_reconciliation.py` | REPORT_ONLY live audit | LEGACY_LIVE_AUDIT |
| `tae_dpe_*` | LEARNING competitive/collaborative | ACTIVE |

## Outputs

| Path | Purpose |
| --- | --- |
| `runtime_outputs/governance/structural_governance.json` | Full step trace + verdict |
| `runtime_outputs/governance/hard_risk.json` | Hard risk evaluation |
| `TAE_STRUCTURAL_GOVERNANCE_REPORT.md` | Operator governance report |
| `TAE_STRUCTURAL_CONSOLIDATION_REPORT.md` | Consolidation summary |
| `runtime_outputs/full_paper_cycle/summary.json` | Legacy-compatible cycle summary |

## Operator command

```bash
python3 tae.py full-paper-cycle
```

## Forbidden (never modified by PAPER cycle)

- `live_bot.py`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt`
- `core/`, `research_core/`
- Broker execution, real money, live promotion
```

### `TAE_MASTER_CONTEXT.md` — Authority order declaration (generated, not SSOT)

```markdown
# TAE Master Session Context (Generated)

**Generated:** 2026-07-05 (post canonical sync)  
**Purpose:** Compressed session bootstrap for AI/human — **not** a new SSOT, design doc, or roadmap replacement.  
**Authority order when in doubt:** `live_bot.py` behavior → `TAE_DEVELOPMENT_PROTOCOL.md` → `PROJECT_BOOK.md` → `SESSION_START.md` → latest sprint/checkpoint report → this file.

---

## 1. Vision & strategic objective

**Trading AI (TAE)** is a **paper-only, analysis-first** trading ecosystem. The live bot selects tickers, scores signals, and manages a paper portfolio. TAE surrounds it with research, evidence, shadow validation, and governance — **without becoming an execution engine**.

**Strategic objective:** Improve **realized profit quality** (exit timing, re-entry discipline, decision sequencing) using shadow evidence **before** any live rule change.

**Competitive advantage:** Median-first historical validation, multi-layer shadow stack (intraday fade → protect → cooldown → replay → knowledge → governor), and a **single live gate** (`RISK_ADVISORY` blocks new BUY only).

**Operating mode:** `ANALYSIS_ONLY` · `PAPER_ONLY` · `NO_BROKER` · `NO_EXECUTION`

---

## 2. Canonical live spine (execution runtime)

| Layer | Module | Artifacts | Live impact |
|-------|--------|-----------|-------------|
| **Execution** | `live_bot.py` | `portfolio.csv`, `live_signals.csv` | **Only** BUY/SELL/STOP execution |
| **Ops** | `bot_controller.py`, `market_session_guard.py`, `dashboard_v2.py` | status files | Start/stop, session gate, UI |
| **Universe** | `watchlist.txt` | — | Bot input |

**Flow:** `watchlist.txt` → yfinance → RSI/SMA score → `live_signals.csv` → `manage_portfolio()` → `portfolio.csv`

**Protected:** `live_bot.py` trading logic, `portfolio.csv`, `live_signals.csv`, `config/settings.py`, `core/trades.py`

---

## 3. Canonical TAE runtimes

### Advisory (live-connected)

```
tae_advisory_index.json → tae_live_advisory.json → live_advisory_runtime.py → live_bot (BUY gate)
                              ↑ governor_enrichment (informational only)
```

- **`RISK_ADVISORY`** → `block_new_buy = true` (X.8 — **only** live block)
- Other actions → advisory/log only
- Governor enrichment does **not** change `block_new_buy` or SELL behavior

### Unified runtime (per-ticker SSOT)

- **File:** `tae_unified_runtime.json` · **Reader:** `UnifiedRuntimeSSOT`
- Feeds bridge, governor, enrichers; does not execute trades

### Shadow / decision (market open — SHADOW_ONLY)

**Orchestrator:** `tae_market_open_intelligence_runner.py` (11 steps):

1. infrastructure_health → 2–4 intraday fade → 5–6 profit protection → 7 cooldown → 8 decision_replay → 9 confidence_evolution → 10 knowledge_base → **11 decision_governor**

| VIEW artifact | Role |
|---------------|------|
| `tae_decision_replay.json` | Replay + readiness |
| `tae_confidence_evolution.json` | Score decay / persistence |
| `tae_knowledge_base.json` | Consolidated learning (VIEW, not SSOT) |
| `tae_decision_governor.json` | Advisory posture + ticker postures (VIEW) |
| `tae_accounting_snapshot.json` | PnL SSOT |

Governor **reads** upstream JSON only — does **not** re-run engines or control live_bot.

### Governance / observability

| Module | Role |
|--------|------|
| `shadow_validation_ledger.py` | BUY path event log (X.9) |
| `tae_infrastructure_health.py` | Autostart/cron/LaunchAgent audit |
| `tae_quick_health_check.py` | Daily ecosystem health |

### Ecosystem batch (separate from market-open stack)

- `tae_full_ecosystem_run.py` / `ecosystem_orchestrator.py` — evidence, ranking, registry (report-only)

---

## 4. Architecture status

```
LIVE          live_bot.py ──► CSVs
                 ▲
ADVISORY       tae_live_advisory.json (X.8 gate + X.DECISION-2B enrichment)
SHADOW         market_open_runner ──► governor VIEW (no live write-back)
```

| Area | Status |
|------|--------|
| Live bot + X.8 gate + X.9 ledger | **Complete** |
| Shadow stack + governor VIEW | **Complete** (`50ebc0b`) |
| Governor → live blocking | **Missing by design** |
| Outcome tracking (X.10) | **Next approved** |
| Event memory ingestion | **Scaffold only** |
| `live_bot_v5_1.py`, V14 threshold stack, `daily_intelligence_runner.py` | **Legacy** |

---

## 5. Milestones

### Current approved milestone

**X.Decision checkpoint — COMPLETED** (`50ebc0b`, 2026-07-05)

- X.KNOWLEDGE-1C, X.DECISION-1, X.DECISION-2A, X.DECISION-2B, X.INFRA-HEALTH-1/2
- Report: `TAE_XDECISION_CHECKPOINT_VALIDATION_REPORT.md`

### Prior milestones (preserved — do not repeat)

X.7B–X.7C advisory stack · X.8 live BUY gate · X.9 shadow ledger · X.REPLAY-1 · X.KNOWLEDGE-1A–1B

### Next approved sprint

**X.10 — Outcome tracking / attribution for blocked BUYs** (requires accumulated `tae_shadow_validation_events.csv`)

**Not approved:** Governor live blocking without architect sign-off.

---

## 6. Forbidden patterns

- Modify `live_bot.py` BUY/SELL/STOP/scoring without explicit sprint
- TAE or governor forcing trades from reports
- Governor/knowledge writing to `portfolio.csv` / `live_signals.csv`
- Competing daily runners; duplicating SSOTs
- Re-running analysis inside governor; `git add .` for sprint commits
- Auto-promoting watchlist/thresholds without operator approval

---

## 7. Mandatory workflow

```
Think → Design → Check existing modules → Implement → Verify → Save → Integrate → Monitor
```

**Session start:** `SESSION_START.md` → this file → `bash tae_checkpoint.sh` → confirm `live_bot.py` canonical.

**Sprint end:** Update `PROJECT_BOOK.md` §1/§12 + sprint history → regenerate this file if canonical docs changed → focused commit when requested.

---

## 8. Quick verification

```bash
cd /Users/book/Desktop/trading_ai
python3 tae_quick_health_check.py
python3 tae_live_advisory_demo.py
python3 tae_market_open_intelligence_runner.py
python3 tae_decision_governor.py
python3 tae_infrastructure_health.py
git diff live_bot.py   # empty unless live sprint
```

---

## 9. Canonical documents

| Document | Role |
|----------|------|
| `PROJECT_BOOK.md` | Full journal — SSOT for project narrative |
| `SESSION_START.md` | Session checklist |
| `TAE_DEVELOPMENT_PROTOCOL.md` | Constitution |
| `TAE_IMPLEMENTATION_ROADMAP.md` | Safe connect sequencing |
| `TAE_XDECISION_CHECKPOINT_VALIDATION_REPORT.md` | Accepted checkpoint evidence |
| **`TAE_MASTER_CONTEXT.md`** | **This file — generated; not SSOT** |

Regenerate this file after canonical doc updates. Do not treat edits here as policy changes.

---

*End of TAE_MASTER_CONTEXT.md*
```

---

## Files inspected

- `PROJECT_BOOK.md`
- `PROJECT_MAP.md`
- `PROJECT_STATUS.md`
- `SESSION_START.md`
- `TAE_ARCHITECTURE.md`
- `TAE_DEVELOPMENT_PROTOCOL.md`
- `TAE_EXISTING_DISCIPLINE_AUDIT.md`
- `TAE_GIT_GOVERNANCE.md`
- `TAE_GOVERNANCE_RESET_SUMMARY.md`
- `TAE_IMPLEMENTATION_ROADMAP.md`
- `TAE_INVESTMENT_COUNCIL_EXISTENCE_AUDIT.md`
- `TAE_MASTER_CONTEXT.md`
- `TAE_MASTER_CONTEXT_AUDIT.md`
- `TAE_MASTER_DEVELOPMENT_WORKFLOW.md`
- `TAE_MASTER_GOVERNANCE_REPORT.md`
- `TAE_STRUCTURAL_GOVERNANCE.md`
- `TAE_UNTRACKED_DOCUMENT_CLASSIFICATION.md`