# TAE Master Sprint Protocol

**Version:** v1  
**Effective:** 2026-07-06  
**Use:** Complete this checklist before every TAE sprint

---

## Pre-sprint checklist (mandatory)

### 1. Identity

- [ ] **Sprint name:** `X.<DOMAIN>-<N> — <Title>`
- [ ] **Workflow phase target:** 0–7 (expected max phase for this sprint)
- [ ] **Checkpoint base:** `git log -1 --oneline`
- [ ] **Problem statement:** (one paragraph)

### 2. Ecosystem audit (Phase 0)

- [ ] Checked `TAE_ECOSYSTEM_INVENTORY.md` for existing modules
- [ ] Checked `TAE_MASTER_SSOT_REGISTRY.md` for field ownership
- [ ] Checked `TAE_DUPLICATION_AUDIT.md` for overlap
- [ ] Checked `TAE_DEPENDENCY_MAP.md` for upstream/downstream
- [ ] Checked `tae.py help` for CLI conflicts
- [ ] Checked dashboard for existing UI

### 3. Build decision

| Decision | Selected |
|----------|----------|
| REUSE existing module | ☐ |
| EXTEND existing module | ☐ |
| BUILD new module | ☐ |
| ARCHIVE / defer | ☐ |

**Rationale:** _______________________________________________

### 4. Scope boundaries

**Allowed files (explicit list):**

```text
-
```

**Forbidden files (always):**

```text
live_bot.py
core/trades.py
core/portfolio.py
portfolio.csv
live_signals.csv
watchlist.txt
broker/
```

**Mode:**

```text
☐ SHADOW_ONLY
☐ NO_BROKER
☐ NO_EXECUTION
☐ NO_PORTFOLIO_CHANGE
☐ NO_ADVISORY_CHANGE
☐ NO_LIVE_CHANGE
☐ NO_COMMIT (unless operator requests)
```

### 5. Architecture (Phase 1)

| Field | Value |
|-------|-------|
| Input SSOT sources | |
| Output artifacts | |
| SSOT owner (new fields) | |
| Live impact | NONE / PARTIAL / YES |
| Promotion path | Phase __ |

### 6. Validation plan (Phase 3)

**Commands:**

```bash
# List exact commands
```

**Acceptance criteria:**

```text
-
```

**Sample size / evidence threshold:**

```text
-
```

### 7. Rollback plan

```text
Revert files: 
Git checkpoint before sprint: 
Live impact if rolled back: NONE
```

### 8. Git checkpoint plan

- [ ] Note base commit before changes
- [ ] Commit message format: `TAE <Sprint ID>: <summary>`
- [ ] Commit only when operator requests
- [ ] No amend unless hook auto-fix per user rules

### 9. Documentation updates

- [ ] Sprint report: `TAE_<SPRINT>_REPORT.md`
- [ ] Update `PROJECT_BOOK.md` if architecture changes (operator approval)
- [ ] Update `SESSION_START.md` if bootstrap changes
- [ ] Update `TAE_MASTER_SSOT_REGISTRY.md` if new SSOT
- [ ] Update `TAE_MASTER_ROADMAP.md` if phase completes

---

## Post-sprint checklist

- [ ] All validation commands PASS
- [ ] Forbidden import check (if CLI touched)
- [ ] Protected files untouched (verify `git diff`)
- [ ] Report includes PASS/FAIL and confirmations
- [ ] Workflow phase achieved documented
- [ ] Recommended next sprint stated

---

## Reusable sprint template

Copy into new sprint report or issue:

```markdown
# TAE <SPRINT_ID> — <Title>

**Date:** YYYY-MM-DD
**Base checkpoint:** <hash> — <message>
**Workflow phase:** 0–<N>
**Mode:** SHADOW_ONLY | NO_BROKER | NO_LIVE_EXECUTION_CHANGE
**Live impact:** NONE | PARTIAL | YES

## Problem statement

<What failure mode or gap this sprint addresses>

## Phase 0 — Audit

| Check | Result |
|-------|--------|
| Existing module | |
| SSOT collision | none / resolved |
| Duplication | REUSE / EXTEND / BUILD |
| CLI | |

## Phase 1 — Architecture

| Field | Value |
|-------|-------|
| Inputs | |
| Outputs | |
| SSOT owner | |
| Upstream | |
| Downstream | |
| Promotion path | Phase __ |

## Phase 2 — Implementation

| File | Change |
|------|--------|
| | |

**Not modified:** live_bot.py, core/, portfolio.csv, ...

## Phase 3 — Validation

```bash
<commands>
```

| Check | Result |
|-------|--------|
| Module run | PASS/FAIL |
| CLI | PASS/FAIL |
| Forbidden imports | PASS/FAIL |

## Sample output

<key metrics>

## Confirmations

| Rule | Status |
|------|--------|
| SHADOW_ONLY | |
| NO_BROKER | |
| NO_LIVE_EXECUTION_CHANGE | |
| NO_COMMIT | |

## Verdict

**PASS / FAIL**

## Recommended next sprint

<ID and one-line scope>
```

---

## Sprint severity classes

| Class | Typical phases | Examples |
|-------|----------------|----------|
| **Audit** | 0 only | X.AUDIT, pre-build audits |
| **Shadow feature** | 0–3 | PIB, PCE, PPG, APPE, growth analytics |
| **Policy integration** | 0–4 | Learning weight updates, knowledge ingest |
| **Advisory candidate** | 0–5 | Bridge enrichment, dashboard advisory |
| **Live change** | 0–7 | X.8-style gate changes — rare |

---

**Governance document — no code changes.**
