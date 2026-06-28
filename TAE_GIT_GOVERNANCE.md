# TAE Git Governance Standard v1.0

**Trading AI Ecosystem — Official Git & Version Control Policy**

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Status | Active |
| Safety mode | ANALYSIS_ONLY \| PAPER_ONLY \| NO_BROKER \| NO_EXECUTION |
| Scope | All Git commits, branches, and tags in the Trading AI Ecosystem repository |
| Companion | [TAE Development Protocol v1.1](TAE_DEVELOPMENT_PROTOCOL.md) |

---

## 1. Purpose

Git history is **part of the ecosystem knowledge system**. It is not a disposable log of file changes — it is a permanent, auditable record of *why* the Trading AI Ecosystem evolved the way it did.

This standard exists so that:

- **History remains readable** — any contributor (human or AI) can understand intent months later
- **History remains auditable** — each checkpoint ties to validation, modules, and phase scope
- **History remains reproducible** — commits correspond to known demos, verdicts, and protected-file states

Every commit should explain **WHY** more than **WHAT**. The diff shows what changed; the message must show why it mattered to TAE.

This document governs Git practice only. It does not modify runtime behavior, live execution, or strategy thresholds.

---

## 2. Commit Categories

All commit messages must begin with one of these **official prefixes**:

| Prefix | Use when |
|--------|----------|
| **DOC** | Documentation only (protocols, journals, README, governance) |
| **ARCH** | Architecture design, interconnection, inventory, systemic integration |
| **CORE** | Live execution core (`core/`, `live_bot.py`) — Human Owner approval required |
| **RUNTIME** | Runtime foundation, orchestrator, workflow, health, learning memory |
| **RESEARCH** | Research modules, analyzers, evidence, simulation, strategy evolution |
| **TEST** | Tests, verification harnesses, demo scripts (when test-only) |
| **FIX** | Bug fixes scoped to one subsystem |
| **REFACTOR** | Internal restructuring with no behavior change |
| **INTEGRATION** | Wiring between modules, gates, pipelines |
| **SECURITY** | Security-related changes, credential hygiene, access controls |
| **RELEASE** | Version tags, release notes, checkpoint bundling |

**Rules:**

- Use exactly one primary prefix per commit
- Prefix is uppercase, followed by colon and space: `PREFIX: Short title`
- If work spans categories, split into separate commits or use the **dominant** category and note the rest in the body

---

## 3. Commit Rules

### 3.1 One logical phase per commit

Each commit represents **one coherent unit of work** — typically one TAE phase deliverable or one focused fix.

Good:

- Phase IX C2 Runtime Foundation (all runtime files + demo + reports for that phase)
- DOC: TAE Development Protocol v1.1

Bad:

- Runtime + orchestrator + documentation + accounting fix in one commit

### 3.2 Never mix these domains in a single commit

| Domain | Examples |
|--------|----------|
| Documentation | `TAE_*.md`, journals, governance |
| Runtime | `research_core/runtime/`, workflow, health |
| Accounting | `research_core/accounting/`, ledger audit |
| Strategy | `core/entry_filter.py`, thresholds, live strategy |
| Orchestrator | `research_core/orchestrator/`, daily runner chain |
| Dashboard | `dashboard_v2.py`, dashboard tools |

If a phase touches multiple domains, **sequence commits** in dependency order (e.g. RESEARCH → INTEGRATION → RUNTIME → DOC).

### 3.3 Protected files

Commits that modify protected live files require:

- Explicit Human Owner approval documented in commit body
- **CORE** or **SECURITY** prefix as appropriate
- Full validation checklist (Section 7)

Default TAE research commits must **not** include changes to:

- `live_bot.py`
- `dashboard_v2.py`
- `config/settings.py`
- `portfolio.csv`
- `core/trades.py`
- `core/portfolio_prices.py`

---

## 4. Commit Message Standard

### Format

```
PREFIX: Short title

Reason:
<Why this change exists — tie to phase, evidence, or bug>

Modules:
<Paths or packages affected>

Validation:
<What was run and results>
```

### Example

```
ARCH: Runtime Foundation Integration

Reason:
Connect Runtime Foundation with Ecosystem Orchestrator as read-only daily state layer.

Modules:
research_core/runtime
research_core/orchestrator

Validation:
Demo OK (tae_phase9_runtime_foundation_demo.py)
py_compile OK
Protected files unchanged
```

### Additional examples

```
DOC: TAE Development Protocol v1.1

Reason:
Add ecosystem constitution, decision hierarchy, and mathematical governance chapters.

Modules:
TAE_DEVELOPMENT_PROTOCOL.md
TAE_DEVELOPMENT_PROTOCOL_SUMMARY.txt

Validation:
Documentation review only — no runtime change
```

```
RESEARCH: Phase VIII B6 Strategy Evolution Daily Runner

Reason:
Single read-only runner chaining candidate registry through paper tracking.

Modules:
research_core/strategy_evolution/daily_runner.py
tae_phase8_strategy_evolution_daily_runner_demo.py

Validation:
Demo OK — STRATEGY_EVOLUTION_DAILY_RUNNER_READY
py_compile OK
Protected files unchanged
```

### Title line rules

- Maximum ~72 characters on the first line
- Imperative mood: "Add", "Fix", "Connect" — not "Added" or "Adding"
- No period at end of title
- Phase ID in body if not obvious from title

---

## 5. Branch Rules

### Protected branches

| Branch | Purpose |
|--------|---------|
| **main** | Integration line; always deployable/readable; merge via reviewed PRs |
| **stable** | Last known good checkpoint; tagged releases only |

### Working branches

| Pattern | Purpose |
|---------|---------|
| **research/** | TAE phase work, analyzers, evidence modules (e.g. `research/phase-ix-c2-runtime`) |
| **feature/** | Focused enhancements with clear scope (e.g. `feature/evidence-engine-refresh`) |
| **hotfix/** | Urgent fixes; requires Human Owner approval for CORE/live paths |

### Branch rules

- Do not commit directly to `main` for multi-file phase work without review
- Branch names: lowercase, hyphen-separated, include phase or topic
- Delete merged research/feature branches after merge when no longer needed
- **No force push** to `main` or `stable` (Section 8)

---

## 6. Release Tags

Tags mark **reproducible ecosystem checkpoints**. Use annotated tags with a message.

### Tag formats

| Format | Example | When |
|--------|---------|------|
| **v1.x** | `v1.0`, `v1.1` | Protocol/governance or major ecosystem milestones |
| **v2.x** | `v2.0` | Breaking architecture or constitution revisions |
| **Phase checkpoint** | `tae-phase-viii-complete` | All Phase VIII deliverables merged and validated |
| **Stable checkpoint** | `stable-2026-06-28` | Orchestrator + runtime + evidence aligned; demos pass |

### Tag message should include

- Phase or release summary
- Key verdicts at tag time (e.g. `ECOSYSTEM_ORCHESTRATOR_READY`)
- Pointer to `TAE_DEVELOPMENT_PROTOCOL` version in effect

Example:

```
git tag -a tae-phase-viii-complete -m "Phase VIII strategy evolution pipeline complete.

Verdicts: CANDIDATE_STRATEGY_REGISTRY_READY through STRATEGY_EVOLUTION_DAILY_RUNNER_READY.
Protocol: TAE Development Protocol v1.1.
Validation: All Phase VIII demos pass; protected files unchanged."
```

---

## 7. Commit Acceptance Checklist

Before any commit is requested or created, confirm:

| # | Check | Required |
|---|-------|----------|
| □ | **py_compile** — all touched Python files compile | Yes |
| □ | **Demo** — phase demo runs exit 0 with expected verdict | Yes (for RESEARCH/RUNTIME/INTEGRATION) |
| □ | **Protected files unchanged** — unless explicitly approved CORE commit | Yes |
| □ | **No duplicated module** — inventory/interconnection checked | Yes |
| □ | **Architecture validation** — as-built matches approved design (Protocol §20) | Yes (non-trivial work) |
| □ | **Integration validation** — fits orchestrator/runtime/canonical map | Yes (when wiring) |
| □ | **Human approval** — Human Owner requested or accepted commit | Yes |

Documentation-only commits (DOC) require Human approval and clear scope; demo/py_compile may be N/A if no Python changed.

---

## 8. Forbidden

The following are **never** permitted under TAE Git Governance v1.0:

1. **Mixed commits** — combining documentation, runtime, accounting, strategy, orchestrator, or dashboard in one commit
2. **Force push** — especially to `main` or `stable`
3. **Undocumented commits** — messages without Reason, Modules, Validation (for non-trivial work)
4. **Anonymous checkpoints** — commits with vague titles ("fix stuff", "updates", "WIP") without phase context
5. **Commit without validation** — no py_compile/demo when Python or demos changed
6. **Commit directly after implementation without review** — Architecture Validation (Protocol §20) must precede commit request
7. **Secrets in Git** — `.env`, API keys, credentials (never commit)
8. **Amend/rebase** that rewrites shared history without Human Owner approval

---

## 9. Git Philosophy

Git history is **part of the Trading AI knowledge system**, alongside:

- `tae_*.json` technical reports
- Evidence Engine items
- Runtime learning memory
- The official Trading AI Journal

Principles:

1. **Every commit should explain WHY more than WHAT** — the diff is the what; the message is the why
2. **Commits are checkpoints, not saves** — prefer fewer, well-scoped commits over noisy micro-commits
3. **Tags are milestones** — use them for phases and stable states, not every merge
4. **Branches are experiments; main is memory** — research branches explore; merged main preserves validated truth
5. **Reproducibility is trust** — if a commit cannot be tied to a demo verdict and validation list, it is not ready

When in doubt, split the commit, document the reason, and wait for Human approval.

---

## Appendix A — Quick Reference

```
PREFIX: Short title

Reason:
...

Modules:
...

Validation:
...
```

**Prefixes:** DOC | ARCH | CORE | RUNTIME | RESEARCH | TEST | FIX | REFACTOR | INTEGRATION | SECURITY | RELEASE

**Branches:** main | stable | research/* | feature/* | hotfix/*

**Never:** mixed domains | force push | unvalidated commits | secrets

---

## Appendix B — Version History

| Version | Date | Summary |
|---------|------|---------|
| 1.0 | 2026-06-28 | Initial Git governance: categories, commit standard, branches, tags, checklist, forbidden actions |

---

*TAE Git Governance Standard v1.0 — Documentation only. No runtime behavior change.*
