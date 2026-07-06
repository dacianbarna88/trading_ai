# TAE Master Roadmap

**Version:** v1  
**Effective:** 2026-07-06  
**Authority:** Official forward roadmap — supersedes ad-hoc sprint ordering for new work  
**Checkpoint baseline:** `a7f9ca1` (APPE V1) through profit stack maturity

---

## Strategic north star

Improve **realized profit quality** (capture, protection, growth) using **shadow evidence first**, **advisory second**, **live last** — per `TAE_MASTER_DEVELOPMENT_WORKFLOW.md`.

**Current state (2026-07-06):**

- Profit **Protection** shadow stack: ~90% mature
- Profit **Growth**: ~25% (design only)
- Live BUY gate: operational (X.8)
- Outcome attribution (X.10): partial implementation

---

## Phase I — Consolidation (now → Q3 2026)

**Goal:** Stabilize SSOT, reduce duplication, complete operational visibility.

| ID | Deliverable | Workflow | Priority |
|----|-------------|----------|----------|
| I-1 | Shared read-only portfolio position parser (`research_core`) | Shadow extend | **P0** |
| I-2 | Dashboard reads PnL from `tae_accounting_snapshot.json` | Shadow/report | P1 |
| I-3 | Dashboard surfaces protect / PPG / APPE summaries | Shadow | P1 |
| I-4 | Quick health checks profit stack JSON freshness | Infra | P1 |
| I-5 | Document dual-governor boundaries in PROJECT_BOOK | Docs | P1 |
| I-6 | CLI completeness audit (`health`, `protect`, `portfolio-protect`, `policy`) | Done ✅ | — |
| I-7 | Archive phase demos from operational docs | Docs | P2 |
| I-8 | Canonical doc sync (MASTER_CONTEXT, PROJECT_BOOK, SESSION_START) | Docs | P2 |

**Exit criteria:** SSOT registry adopted; no new module duplicates PnL or position parsing.

---

## Phase II — Profit Growth (after consolidation)

**Goal:** Measure and improve profit capture — not rebuild protection.

| ID | Deliverable | Workflow | Depends |
|----|-------------|----------|---------|
| II-1 | **X.PROFIT-GROWTH-1** — Profit Growth Analytics SSOT | Phase 0–3 | I-1 recommended |
| II-2 | Opportunity Cost Ledger (persisted time series) | Phase 0–3 | II-1 |
| II-3 | Winner DNA Profiler (shadow profiles) | Phase 0–3 | II-1, memory engine |
| II-4 | Dynamic Profit Targets (shadow rules v2) | Phase 0–3 | protect shadow |
| II-5 | Growth Simulation Lab | Phase 0–3 | validation, replay |
| II-6 | Capital Rotation Engine | Phase 0–3 | II-1, accounting |
| II-7 | Portfolio Evolution Engine | Phase 0–3 | II-1, PPG |

**Explicitly not in Phase II:** Live rule changes, new BUY/SELL logic, advisory gate changes.

**Exit criteria:** Growth analytics SSOT operational; opportunity cost series ≥30 days; winner profiles for ≥50% of open book.

---

## Phase III — Learning & Policy

**Goal:** Close the evidence loop on shadow decisions.

| ID | Deliverable | Workflow | Depends |
|----|-------------|----------|---------|
| III-1 | APPE history accumulation (scheduled `tae.py policy`) | Phase 2–4 | APPE ✅ |
| III-2 | X.10 outcome closure at scale | Phase 3 | shadow events volume |
| III-3 | Policy accuracy thresholds documented | Phase 3 | III-1 |
| III-4 | Committee reweighting from validated outcomes | Phase 4 | III-2, III-3 |
| III-5 | Knowledge ingest: APPE + X.10 → knowledge base | Phase 4 | III-2 |
| III-6 | Context learning from validated protect outcomes | Phase 4 | PCE v2 |

**Exit criteria:** Policy accuracy measurable; knowledge base contains validated policy entries; false positive rate documented.

---

## Phase IV — Advisory Promotion

**Goal:** Enrich advisory layer with evidence — not expand live blocking by default.

| ID | Deliverable | Workflow | Depends |
|----|-------------|----------|---------|
| IV-1 | Advisory candidate tests (enrichment-only) | Phase 5 | III-2 |
| IV-2 | Operator review playbook | Phase 6 | IV-1 |
| IV-3 | Governor enrichment expansion (informational) | Phase 5 | III-5 |
| IV-4 | Dashboard advisory drill-down | Phase 5 | I-3 |
| IV-5 | Counterfactual report for blocked BUYs | Phase 3–5 | III-2 |

**Default:** Enrichment only — `block_new_buy` unchanged unless separate approved sprint.

**Exit criteria:** Operator sign-off on at least one advisory enrichment; counterfactual report in dashboard.

---

## Phase V — Live Evolution

**Goal:** Minimal, gated live changes with rollback.

| ID | Deliverable | Workflow | Depends |
|----|-------------|----------|---------|
| V-1 | Live change proposal document | Phase 6 | IV-2 |
| V-2 | Dedicated live integration sprint | Phase 7 | V-1 approval |
| V-3 | Small gated rollout + monitoring | Phase 7 | V-2 |
| V-4 | Rollback verification | Phase 7 | V-2 |
| V-5 | Post-live shadow comparison | Phase 3 | V-3 |

**Rule:** No Phase V work without explicit operator approval and completed Phase III evidence.

---

## Completed milestones (reference)

| Checkpoint | Sprint | Capability |
|------------|--------|------------|
| `7f419f2` | PIB V1 | Profit intelligence brain |
| `ea84ad2` | PIB V2 | PSP survival probability |
| `663cc15` | PIB V3 | Memory dedupe |
| `663cc15+` | PDC V1/V2 | Decision committee + learning |
| `663cc15+` | PCE V1/V2 | Context engine + adaptive weights |
| `1b40d6e` | PDG + PPG | Profit + portfolio governors |
| `a7f9ca1` | APPE V1 | Adaptive profit policy memory |
| — | X.AUDIT | Ecosystem consolidation audit |
| — | MASTER v1 | Development workflow governance |

---

## Immediate next sprint (recommended)

```text
X.PROFIT-GROWTH-1 — Profit Growth Analytics SSOT
```

**Prerequisites met:**

- Master workflow saved (this governance pack)
- Profit protection stack mature
- SSOT registry defined

**Scope:** Phase 0–3 only. Read-only. No live/advisory change.

---

## Roadmap governance

- Update this file when a phase item completes or is deferred
- Deferrals require reason in sprint report
- New modules must map to a phase ID before build starts
- Legacy `TAE_ROADMAP.md` / `TAE_IMPLEMENTATION_ROADMAP.md` — historical reference only

---

**Governance document — no code changes.**
