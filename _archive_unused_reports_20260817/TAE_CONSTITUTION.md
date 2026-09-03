# TAE Constitution

**Trading AI Engine — Official Project Constitution**

| Field | Value |
|-------|-------|
| Version | **2.2** |
| Status | **CANONICAL** (sole documentary SSOT for project state) |
| Effective | 2026-08-03 |
| Architecture | **`ARCHITECTURE_FREEZE`** — see §3.1 |
| Prior | v2.1 (same day); process companion `TAE_DEVELOPMENT_PROTOCOL.md` v1.1 |
| Safety mode | `PAPER_ONLY` \| `NO_BROKER` \| `NO_LIVE_PROMOTION` |
| Philosophy | Unchanged from Protocol §15–§21 |

> **This document is the single constitutional SSOT.**  
> `PROJECT_BOOK.md` and `SESSION_START.md` are synced operational mirrors. On conflict, **this file governs**.  
> Development process details: `TAE_DEVELOPMENT_PROTOCOL.md`.

---

## 1. Fundamental Principles

1. **Evidence over intuition.** Measured reports and verdicts authorize action; narrative does not.
2. **Statistics over assumptions.** Sample size, expectancy, ROI, and cohort evidence govern economic change.
3. **Validation over opinions.** Paper validation and promotion gates cannot be waived by preference.
4. **Integration over local optimization.** A local win that breaks ecosystem coherence is rejected.
5. **Long-term profitability over short-term cosmetics.** Single-trade anecdotes do not override portfolio evidence.
6. **Human Owner supervises live.** No stage auto-promotes to broker/live execution.
7. **Do not rebuild what exists.** Extend canonical modules; forbid competing runners and parallel authorities.
8. **Knowledge accumulates.** Learning appends; it does not silently discard validated history.
9. **No strategy is permanent.** Every strategy remains a candidate until statistically outperformed or invalidated.
10. **PAPER is the economic proving ground.** Economic patches prove in PAPER before any live consideration.

---

## 2. Canonical Architecture

```
Canonical full-paper-cycle (single orchestration)
        │
        ├── V1 benchmark PAPER book
        │     portfolio / orders / equity / learning  (paper_execution/)
        │
        ├── V2 challenger PAPER book
        │     portfolio / cycles / journals / learning tags  (parallel_paper/v2/)
        │     via library arm — NO daemon, NO LaunchAgent
        │
        ├── Decision Brain (PDE) → paper decisions
        ├── Binding Decision Brain SKIP gate (PAPER new entries — provisional)
        ├── Hard Risk (−3% / −5%) crystallization
        ├── Settlement · daily equity · accounting snapshots
        └── Longitudinal / canonical learning (strategy-isolated)
```

| Layer | Canonical owner |
|-------|-----------------|
| Orchestration | `python3 tae.py full-paper-cycle` / structural governance |
| V1 PAPER book | `runtime_outputs/paper_execution/` |
| V2 PAPER book | `runtime_outputs/parallel_paper/v2/` |
| Decision Brain | `tae_paper_decision_engine.py` (`action` field) |
| Entry SKIP gate | `tae_paper_execution` + V2 buy policy (`DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED`) |
| Dual strategy hook | `tae_canonical_dual_strategy.py` inside FPC |
| Live runtime (outside PAPER economic spine) | `live_bot.py` — Human Owner |
| Broker | **OFF** for TAE economic work |

**Capital baselines (separate historical SSOT, not a split purse):** V1 30 000 · V2 30 000.

---

## 3. Governance

### Authority order

1. **Human Owner** — live strategy, commits, promotion approval  
2. **This Constitution (v2.2)** — project-state and hard rules  
3. **`TAE_DEVELOPMENT_PROTOCOL.md`** — how work is designed/verified  
4. **`TAE_GIT_GOVERNANCE.md`** — commit/branch discipline  
5. Sprint verdict artifacts (`TAE_*.md` / `tae_*.json`) — factual status  
6. `PROJECT_BOOK.md` / `SESSION_START.md` — operational journal & session bootstrap (synced to this file)

### Infrastructure status

| Item | Status |
|------|--------|
| Infrastructure closure | **`TAE_INFRASTRUCTURE_CLOSED`** |
| Canonical FPC | **ACTIVE** |
| Dual strategy | **`V1_V2_DUAL_STRATEGY_ACTIVE`** |
| Parallel-paper daemon | **ABSENT** (must stay unrestored) |
| Parallel-paper LaunchAgent | **ABSENT** |
| Scheduler | Canonical FPC / health path only |
| Broker | **OFF** |
| Live promotion | **Blocked** (`live_promotion_allowed=false`) |
| Architecture | **`ARCHITECTURE_FREEZE`** (see §3.1) |

### Sprint discipline

```
Think → Design → Audit existing → Implement minimal → Verify → Measure → (Commit only if Owner asks)
```

### 3.1 ARCHITECTURE_FREEZE

**Any structural modification is forbidden** until **all three** conditions exist:

1. **Economic audit** — measured impact on the PAPER books (or explicit scoped audit deliverable)  
2. **Statistical proof** — sample / expectancy / counterfactual / cohort evidence, not narrative alone  
3. **Explicit Owner approval** — Human Owner authorizes the structural change in writing (sprint brief or recorded directive)

**Absent these three, only the following are permitted:**

| Allowed | Examples |
|---------|----------|
| Bug fixes | Incorrect behavior vs existing contract; no new architecture |
| Maintenance | Health, marks freshness, test hermeticity, dependency/compat fixes |
| Compatibility | Keep FPC / V1 / V2 / docs / flags working as already designed |
| Documentation updates | Constitution, Book, Session, audits, reports |

**Structural (frozen without the triad):** new engines, new strategies (e.g. V3), new gate engines, dual-runtime / daemon / LaunchAgent restores, SELL or Hard Risk semantic redesign, learning-algorithm redesign, capital/accounting architecture splits, competing Decision Brain, FPC replacement, broker/LIVE economic enablement paths.

Provisional PAPER gates already under forward cohort (e.g. Binding Decision Brain SKIP) may continue **measurement and rollback-via-flag**; expanding their architecture or promoting them to permanent/LIVE still requires the triad.

---

## 4. Economic Rules

1. **Prove before patch.** Statistical / counterfactual proof precedes binding economic changes.
2. **Minimal economic patches.** Prefer one binding rule with attribution over architecture rewrites.
3. **Separate books.** V1 and V2 cash, positions, equity, and learning must not cross-contaminate.
4. **Attribution required.** Entries and blocks carry `strategy_id`, decision ids, and economic class.
5. **Forward cohorts before declaring profit.** Activation ≠ profitability.
6. **Counterfactual honesty.** Report avoided loss and missed profit; do not invent fills.

### Binding Decision Brain SKIP (provisional PAPER gate)

This gate is **not** a permanent constitutional truth. It is an economic experiment under continuous validation.

| Aspect | Status |
|--------|--------|
| PAPER | **ACTIVE** (`DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED`, default true) |
| LIVE / broker | **OFF** — not in scope |
| Technical validation | **PASS** (suite + attribution + isolation) |
| Statistical prior | `GLOBAL_ENTRY_GATE_PROVEN` (historical counterfactual) |
| Forward cohort | **ACTIVE** — `BINDING_SKIP_GATE_FORWARD_COHORT` (outcomes PENDING until mature) |
| Permanence | **NOT DECLARED** — continuous economic validation decides keep, soften, or rollback |
| Rollback | `DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED=false` (PAPER) |

| Rule while ACTIVE in PAPER | Scope |
|----------------------------|-------|
| Canonical Decision Brain `SKIP` / `SKIP_PAPER` → block new entry | V1 **new BUY**; V2 **OPEN** only |
| Block reason | `BLOCKED_DECISION_BRAIN_SKIP` |
| Economic class | `ENTRY_BLOCKED_BY_DECISION_BRAIN_SKIP` |
| Out of scope | V2 ADD · SELL · Hard Risk · existing positions · LIVE |

**Not hard gates (rejected pending new proof):** PPG PROTECT alone · Forecast 7D NEGATIVE alone · Score 100 veto.

---

## 5. What Is Forbidden

- Auto-promote PAPER → LIVE / broker without Owner approval and economic proof  
- Restore parallel-paper **daemon** or retired **LaunchAgents**  
- Create V3 or a second FPC / second accounting engine  
- Cross-strategy cash or portfolio mutation  
- Hard-gate PPG / 7D / score100 without new global proof  
- Change **SELL** or **Hard Risk** semantics outside an explicit Owner-approved sprint  
- Invent fills/journals for runtime proof (TEST_ONLY fixtures only)  
- Competing Decision Brain / gate engine  
- Silent live execution path changes  
- Treat any provisional PAPER gate as permanent without mature forward outcomes  
- Structural change under **ARCHITECTURE_FREEZE** without economic audit + statistical proof + Owner approval  
- Force-push to main; commit without Owner request; commit secrets  

---

## 6. V1 and V2

| | V1 | V2 |
|--|----|----|
| Role | Benchmark | Challenger |
| Status | **ACTIVE** | **ACTIVE** |
| Dual verdict | **`V1_V2_DUAL_STRATEGY_ACTIVE`** | same FPC |
| Portfolio | `paper_execution/paper_portfolio.json` | `parallel_paper/v2/portfolio.json` |
| Entry | PDE `BUY_PAPER` via `execute_decision` | `OPEN_CYCLE` / `ADD_TRANCHE` |
| SKIP gate (while PAPER-active) | Blocks **new BUY** on SKIP | Blocks **OPEN** on SKIP; **ADD untouched** |
| Trailing | Canonical PAPER trailing | `tae_strategy_v2_trailing.py` (not LIVE `core/trailing.py`) |
| Learning | Canonical paper learning | Tagged `strategy_id=V2`; no V1 contamination |

---

## 7. Learning

- Learning runtime and longitudinal memory are the learning SSOT.  
- Learning may remain `TESTING` with soft `influence_delta`.  
- Binding entry vetoes come from **explicit gates**, not every annotation.  
- Provenance must stay reconstructible: outcome → decision delta → authority → entry/block.

---

## 8. Decision Brain

| Item | Value |
|------|-------|
| Owner | `tae_paper_decision_engine.py` |
| Canonical field | `action` |
| Values | `BUY_PAPER`, `SKIP_PAPER`, `HOLD_PAPER`, `SELL_PAPER`, `REDUCE_PAPER`, `PROTECT_PAPER`, `ROTATE_PAPER` |
| Memory | `runtime_outputs/longitudinal_memory/decisions.jsonl` |
| PAPER entry (while SKIP gate ACTIVE) | Resolved **SKIP** → new entry unauthorized |

---

## 9. Hard Risk

| Item | Stance |
|------|--------|
| Semantics | **PROTECTED** — unchanged by entry-gate work |
| Role | Downstream crystallization (−3% / −5% family) |
| Forbidden | Using threshold edits as a substitute for entry quality |

---

## 10. SELL

| Item | Stance |
|------|--------|
| Semantics | **PROTECTED** — unchanged by entry-gate work |
| Scope | Exits independent of SKIP entry gate |

---

## 11. Roadmap (phased)

### FAZA I — Infrastructure Closed

**Status: DONE** (`TAE_INFRASTRUCTURE_CLOSED`)

Canonical FPC, health, accounting, settlement, learning handoff, LaunchAgent cleanup, no restored daemon.

### FAZA II — Economic Validation

**Status: IN PROGRESS**

| Item | Status |
|------|--------|
| Dual V1/V2 books | DONE (`V1_V2_DUAL_STRATEGY_ACTIVE`) |
| Loss decomposition / entry causality / global entry-gate proof | DONE |
| Binding Decision Brain SKIP in PAPER | ACTIVE (provisional) |
| Forward cohort measurement | ACTIVE / PENDING maturity |
| Decide permanence of SKIP gate | OPEN — continuous validation |
| Optional soft biases (PPG / 7D / score) | Only after new proof; not hard gates by default |

### FAZA III — Institutional Optimization

**Status: NOT STARTED**

Process, reporting, capital utilization, and institutional controls — only after FAZA II outcomes are mature. No V3. No casual SELL/Hard Risk rewrites.

### FAZA IV — LIVE

**Status: FORBIDDEN until proven**

LIVE / broker enablement of economic gates requires:

1. Mature PAPER economic evidence  
2. Explicit Human Owner approval  
3. Constitutional amendment or Owner directive recorded in sprint verdict  

Default: **Broker OFF**, `live_promotion_allowed=false`.

---

## 12. SSOT Map

| Responsibility | SSOT |
|----------------|------|
| Project constitution | **`TAE_CONSTITUTION.md`** (this file) |
| Session bootstrap | `SESSION_START.md` |
| Project journal | `PROJECT_BOOK.md` |
| Development process | `TAE_DEVELOPMENT_PROTOCOL.md` |
| Git rules | `TAE_GIT_GOVERNANCE.md` |
| V1 portfolio | `runtime_outputs/paper_execution/paper_portfolio.json` |
| V2 portfolio | `runtime_outputs/parallel_paper/v2/portfolio.json` |
| PAPER decisions | `runtime_outputs/paper_decisions/paper_decisions.json` |
| SKIP blocks / cohort | `decision_brain_skip_blocks.jsonl` / `binding_skip_gate_forward_cohort.jsonl` |
| FPC verdict | `runtime_outputs/governance/structural_governance.json` |

---

## Appendix A — Document classes

| Path | Class |
|------|-------|
| `TAE_CONSTITUTION.md` | **CANONICAL** (+ ARCHITECTURE_FREEZE) |
| `PROJECT_BOOK.md` | **CANONICAL** operational journal (synced) |
| `SESSION_START.md` | **CANONICAL** session bootstrap (synced) |
| `TAE_DEVELOPMENT_PROTOCOL.md` | Process companion · **SUPERSEDED** as sole constitution |
| `TAE_GIT_GOVERNANCE.md` | Governance companion |
| `TAE_CONSTITUTION_RECOVERY_REPORT.md` | **LEGACY** |
| `PROJECT_STATUS.md` / `PROJECT_MAP.md` / `TAE_MASTER_CONTEXT.md` / `TAE_ARCHITECTURE.md` | **LEGACY** / derived — not SSOT |
| `constitutional_evolution.json` | Runtime artifact — not this constitution |

---

## Appendix B — Version history

| Version | Date | Summary |
|---------|------|---------|
| 2.2 | 2026-08-03 | **ARCHITECTURE_FREEZE** — structural change requires audit + statistical proof + Owner approval |
| 2.1 | 2026-08-03 | Documentation closure: provisional SKIP language; FAZA I–IV roadmap; Book/Session synced |
| 2.0 | 2026-08-03 | First standalone constitution file |
| 1.1 | 2026-06-28 | Protocol constitution text |

---

*TAE Constitution v2.2 — Documentary SSOT. Does not alter runtime by itself.*
