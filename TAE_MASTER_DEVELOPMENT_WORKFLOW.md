# TAE Master Development Workflow

**Version:** v1  
**Effective:** 2026-07-06  
**Authority:** Governs all future TAE development sprints  
**Mode default:** SHADOW_ONLY until Phase 7

---

## Purpose

TAE has grown into a multi-layer ecosystem (~267 root Python modules, dual shadow spines, live advisory gate). This document establishes the **permanent development workflow** to prevent chaotic growth, SSOT drift, and premature live integration.

**Golden rule:** No module reaches live execution without passing every prior phase and explicit operator approval.

---

## Workflow overview

```
Phase 0 — Ecosystem Audit
        ↓
Phase 1 — Architecture Design
        ↓
Phase 2 — Shadow Build
        ↓
Phase 3 — Validation
        ↓
Phase 4 — Committee / Policy Integration
        ↓
Phase 5 — Advisory Candidate
        ↓
Phase 6 — Operator Approval
        ↓
Phase 7 — Live Integration
```

Each phase has **entry criteria**, **deliverables**, and **exit gates**. Skipping phases is forbidden unless architect explicitly documents an exception in the sprint report.

---

## Phase 0 — Ecosystem Audit

**Required before any new sprint.**

### Must check

| Check | Reference artifact |
|-------|-------------------|
| Existing modules | `TAE_ECOSYSTEM_INVENTORY.md` |
| SSOT ownership | `TAE_MASTER_SSOT_REGISTRY.md`, `TAE_SSOT_AUDIT.md` |
| Dependency map | `TAE_DEPENDENCY_MAP.md` |
| Duplication risk | `TAE_DUPLICATION_AUDIT.md` |
| CLI integration | `tae.py` dispatcher, `TAE_MASTER_ARCHITECTURE.md` |
| Dashboard integration | `dashboard_v2.py`, `dashboard_tae_command_center.py` |
| Validation history | Prior `TAE_*_REPORT.md`, test modules |

### Exit gate

- Sprint problem is **not already solved** by an existing module
- Reuse / extend / build decision documented
- No SSOT collision identified (or collision resolved in design)

### Deliverables

- Pre-build audit section in sprint report OR reference to X.AUDIT / master audit
- Updated gap analysis if scope is strategic

---

## Phase 1 — Architecture Design

**Required before writing production code.**

### Must define

| Field | Description |
|-------|-------------|
| Problem solved | One sentence — what failure mode or gap |
| Input | Files, APIs, SSOT sources (read-only list) |
| Output | JSON / MD / CSV artifacts |
| SSOT owner | Which module owns new fields |
| Downstream consumers | Who reads the output |
| Upstream producers | Who must run first |
| Mode | SHADOW_ONLY / ADVISORY / LIVE |
| Live impact | YES / PARTIAL / NO |
| Promotion path | Which phase this module targets (2–7) |

### Exit gate

- Design doc or sprint spec approved (self-review minimum)
- No forbidden file modifications planned
- Forbidden imports documented (`research_core` / `pandas` only where already allowed)

### Deliverables

- Architecture section in sprint report
- Update `TAE_MASTER_SSOT_REGISTRY.md` if new SSOT field introduced

---

## Phase 2 — Shadow Build

**Default build phase for all new intelligence modules.**

### Mandatory rules

```text
SHADOW_ONLY
NO_BROKER
NO_EXECUTION
NO_PORTFOLIO_CHANGE
NO_ADVISORY_CHANGE
NO_LIVE_CHANGE
```

### Protected files (never modify in Phase 2)

```text
live_bot.py
core/
portfolio.csv
live_signals.csv
watchlist.txt
```

### Build standards

- Stdlib-first for CLI modules unless existing pattern uses approved deps
- Read upstream JSON/CSV only — do not re-run upstream engines inside VIEW composers
- Emit JSON + MD artifacts
- Include `mode`, `live_trading_impact`, `no_broker` in JSON schema
- Integrate into `tae.py` CLI when user-facing

### Exit gate

- Module runs exit 0
- Artifacts generated
- Forbidden import check passes
- No protected files modified

---

## Phase 3 — Validation

**Required before any promotion discussion.**

### Must require

| Requirement | Minimum standard |
|-------------|------------------|
| Historical validation | Backtest or replay on accumulated data where applicable |
| Shadow evidence | At least one full pipeline run with real artifacts |
| Sample size threshold | Document N observations / tickers / days |
| False positive rate | Document if classifier / policy module |
| Comparison vs baseline | vs HOLD, prior sprint, or rules v1 |

### Validation commands (typical)

```bash
python3 <module>.py
python3 tae.py <command>          # if CLI integrated
python3 -m py_compile <module>.py
python3 <module>_test.py          # if tests exist
# Forbidden imports check (stdlib CLI modules)
```

### Exit gate

- Sprint report includes PASS/FAIL
- Sample outputs documented
- Known limitations listed

---

## Phase 4 — Committee / Policy Integration

**New outputs integrate into committee/policy layers — never directly into live.**

### Integration targets (by domain)

| Domain | Integration point |
|--------|-------------------|
| Per-ticker profit | PDC → PDG (`tae_profit_decision_governor.py`) |
| Portfolio | PPG → APPE (`tae_portfolio_profit_governor.py`, `tae_adaptive_profit_policy_engine.py`) |
| Cross-domain advisory | Knowledge base ingest → `tae_decision_governor.py` VIEW |
| Signal / entry | Confidence evolution → knowledge base |

### Rules

- New module **feeds** committee/policy; does not bypass them
- Weight / policy updates must be conservative until validation matures
- Persist learning state in JSON with stable dedupe keys (no timestamp in observation keys)

### Exit gate

- Downstream VIEW refreshes correctly when upstream run
- No live_advisory_bridge or live_bot changes

---

## Phase 5 — Advisory Candidate

**Only after Phase 3 validation evidence exists.**

### Criteria

- Validation gates passed or explicitly WATCH with documented reason
- False positive rate acceptable for operator review
- SSOT fields stable
- Enrichment-only path identified (default) vs gate-change path (rare)

### Allowed changes

- Read-only enrichment in `tae_live_advisory.json` (e.g. `governor_enrichment`)
- New advisory report sections in dashboard

### Forbidden without Phase 6–7

- Changing `block_new_buy` logic
- Changing SELL behavior
- Auto-promotion from shadow verdict

### Exit gate

- Advisory candidate documented in sprint report
- Counterfactual / outcome tracking plan if gate change proposed

---

## Phase 6 — Operator Approval

**Explicit human approval required.**

### Operator must confirm

- [ ] Reviewed validation report
- [ ] Understands live impact scope (BUY only / none / full)
- [ ] Rollback plan exists
- [ ] Git checkpoint identified
- [ ] PROJECT_BOOK / SESSION_START update planned

### Record

- Approval date, checkpoint hash, scope in sprint report
- **No implied approval** from AI agent completion

---

## Phase 7 — Live Integration

**Only via dedicated sprint — never bundled with shadow build.**

### Requirements

- Separate sprint ID (e.g. X.LIVE-*)
- Minimal diff to live path
- Rollback tested
- Post-integration validation run
- Shadow stack still operational for comparison

### Allowed live touchpoints

| Module | Allowed change |
|--------|----------------|
| `live_bot.py` | Only with Phase 6 approval |
| `live_advisory_runtime.py` | BUY gate threshold / block logic |
| `live_advisory_bridge.py` | Advisory composition |

### Default

**Most sprints never reach Phase 7.** Profit intelligence stack is designed to remain SHADOW_ONLY through Phase 4 indefinitely until evidence demands otherwise.

---

## Workflow binding

All future sprints must declare in report header:

```text
Workflow phase: 0–7
Mode: SHADOW_ONLY | ADVISORY | LIVE
Live impact: NONE | PARTIAL | YES
SSOT fields touched: [list or none]
```

Reference documents:

- `TAE_MASTER_SPRINT_PROTOCOL.md` — per-sprint checklist
- `TAE_MASTER_SSOT_REGISTRY.md` — field ownership
- `TAE_MASTER_ROADMAP.md` — phase priorities
- `TAE_MASTER_ARCHITECTURE.md` — spine map

---

**Governance document — no code changes.**
