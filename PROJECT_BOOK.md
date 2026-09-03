# Trading AI — PROJECT BOOK (Canonical Journal)

**Last updated:** 2026-08-03  
**Constitution SSOT:** [`TAE_CONSTITUTION.md`](TAE_CONSTITUTION.md) **v2.2**  
**Governance mode:** `PAPER_ONLY` \| `NO_BROKER` \| `NO_LIVE_PROMOTION` \| **`ARCHITECTURE_FREEZE`**  
**Latest documentation sprint:** `TAE_CANONICAL_DOCUMENTATION_CLOSURE`

> **Read first each session:** [`SESSION_START.md`](SESSION_START.md)  
> **On conflict:** Constitution governs. This book must stay synced to it.

---

## 1. Current Project Status

| Component | Status |
|-----------|--------|
| Infrastructure | **`TAE_INFRASTRUCTURE_CLOSED`** |
| Canonical FPC | **ACTIVE** |
| V1 (benchmark) | **ACTIVE** |
| V2 (challenger) | **ACTIVE** |
| Dual strategy | **`V1_V2_DUAL_STRATEGY_ACTIVE`** |
| Decision Brain (PDE) | **ACTIVE** |
| Binding Decision Brain SKIP | **ACTIVE in PAPER** (provisional — forward cohort decides permanence) |
| Forward cohort | **ACTIVE** (`BINDING_SKIP_GATE_FORWARD_COHORT`) |
| Learning | **ACTIVE** (strategy-isolated) |
| Hard Risk | **PROTECTED** |
| SELL | **PROTECTED** |
| Broker | **OFF** |
| Live promotion | **Blocked** |
| Parallel-paper daemon / LaunchAgent | **ABSENT** (do not restore) |
| Documentation | **CLOSED** |
| Architecture | **`ARCHITECTURE_FREEZE`** |

---

## 2. Canonical Architecture

```
python3 tae.py full-paper-cycle
        │
        ├── V1 PAPER book     runtime_outputs/paper_execution/
        ├── V2 PAPER book     runtime_outputs/parallel_paper/v2/
        │                      (library arm only — no daemon)
        ├── Decision Brain    tae_paper_decision_engine.py
        ├── SKIP entry gate   PAPER new V1 BUY / V2 OPEN (provisional)
        ├── Hard Risk         −3% / −5% crystallization (PROTECTED)
        ├── Settlement · daily equity · accounting
        └── Learning          strategy_id-separated
```

| Layer | Owner / path |
|-------|----------------|
| FPC / structural governance | `tae.py full-paper-cycle`, `tae_structural_governance.py` |
| V1 portfolio / orders / equity | `runtime_outputs/paper_execution/` |
| V2 portfolio / cycles / journals | `runtime_outputs/parallel_paper/v2/` |
| Dual hook | `tae_canonical_dual_strategy.py` |
| Decisions | `runtime_outputs/paper_decisions/` |
| Live bot (non-PAPER economic spine) | `live_bot.py` — Human Owner |
| Capital baselines | V1 30 000 · V2 30 000 (separate SSOT) |

---

## 3. V1 (Benchmark)

- Canonical PAPER book under `paper_execution/`
- Entry via PDE `BUY_PAPER` → `execute_decision`
- While SKIP gate is PAPER-active: **new** BUY blocked if Decision Brain resolves to `SKIP_PAPER`
- Learning consumes V1 paper paths only for V1 attribution
- Do not merge V1 cash/positions with V2

---

## 4. V2 (Challenger)

- Challenger book under `parallel_paper/v2/`
- Runs inside the **same** FPC via library (`_run_v2_arm`) — **no** daemon, **no** LaunchAgent
- Entry: `OPEN_CYCLE` / `ADD_TRANCHE` via V2 buy policy
- While SKIP gate is PAPER-active: **OPEN** blocked on SKIP; **ADD not gated** by this sprint
- Trailing helpers: `tae_strategy_v2_trailing.py` (must not overwrite LIVE `core/trailing.py`)
- All outcomes tagged `strategy_id=V2`

---

## 5. Decision Brain

| Item | Value |
|------|-------|
| Module | `tae_paper_decision_engine.py` |
| Field | `action` |
| Values | `BUY_PAPER`, `SKIP_PAPER`, `HOLD_PAPER`, `SELL_PAPER`, … |
| Memory | `runtime_outputs/longitudinal_memory/decisions.jsonl` |
| Role | Final PAPER decision authority for the V1 spine; V2 consumes PDE/memory verdict for OPEN gate |

Conflict / STRONG BUY may still *propose* BUY; the provisional SKIP **entry gate** is the binding check for new PAPER risk.

---

## 6. Binding Decision Brain SKIP Gate

**Not a permanent truth.** Documented honestly:

| Aspect | Status |
|--------|--------|
| PAPER | ACTIVE (flag `DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED`) |
| Technical validation | PASS |
| Prior statistical proof | `GLOBAL_ENTRY_GATE_PROVEN` |
| Forward cohort | ACTIVE — permanence **not** declared |
| LIVE | NO |
| Rollback | set flag `false` |

Scope: V1 new BUY · V2 OPEN. Not: ADD · SELL · Hard Risk · existing positions.

Journals: `decision_brain_skip_blocks.jsonl`, `binding_skip_gate_forward_cohort.jsonl`.

---

## 7. Hard Risk

- Semantics **PROTECTED**
- Role: crystallize drawdown (−3% STOP / −5% CRITICAL family)
- Confirms vulnerability; does not replace entry discipline
- Do not retune thresholds as a substitute for entry quality

---

## 8. SELL

- Semantics **PROTECTED**
- Exits (protective, trailing, Hard Risk closes) independent of SKIP entry gate
- Do not couple SELL to entry experiments without explicit Owner-approved sprint

---

## 9. Learning

- ACTIVE with strategy isolation (`strategy_id`)
- May remain `TESTING` / soft `influence_delta`
- Binding vetoes = explicit gates (e.g. SKIP), not every annotation
- Provenance: outcome → decision delta → authority → entry/block

---

## 10. Full-Paper-Cycle (FPC)

- Single canonical orchestration: `python3 tae.py full-paper-cycle`
- Includes dual-strategy arm after V1 path
- Health: `python3 tae.py health`
- Suite: `python3 tae.py test`
- Mark-to-market: `python3 tae.py paper-mark-to-market`
- Host mark staleness (`ALL_STALE`) is an ops issue — not a license to restore daemons

---

## 11. Accounting

| Book | Portfolio SSOT | Equity |
|------|----------------|--------|
| V1 | `paper_execution/paper_portfolio.json` | `paper_daily_equity.jsonl` |
| V2 | `parallel_paper/v2/portfolio.json` | V2 journals / snapshots under `v2/` |

Rules: no cross-book cash mutation; attribution must carry `strategy_id`; inventing fills forbidden.

---

## 12. Governance

Authority: Human Owner → **Constitution v2.2** → Development Protocol → Git Governance → sprint artifacts → this Book / Session Start.

### ARCHITECTURE_FREEZE

Structural change is **forbidden** until **all three** exist: (1) economic audit, (2) statistical proof, (3) explicit Owner approval.

Without the triad, only: bug fixes · maintenance · compatibility · documentation.

Forbidden under freeze (examples): new engines, V3, daemon/LaunchAgent restore, SELL/Hard Risk redesign, competing Decision Brain, FPC replacement, LIVE economic enablement.

Provisional PAPER SKIP gate may continue measurement/flag rollback; expanding architecture or LIVE promotion still requires the triad.

Forbidden (see Constitution §5): auto LIVE promote; restore daemon/LA; V3; second FPC/accounting engine; PPG/7D/score100 hard gates without new proof; casual SELL/HR changes; structural change without the freeze triad.

---

## 13. Roadmap (aligned with Constitution)

| Phase | Name | Status |
|-------|------|--------|
| **FAZA I** | Infrastructure Closed | **DONE** |
| **FAZA II** | Economic Validation | **IN PROGRESS** (SKIP provisional + cohort) |
| **FAZA III** | Institutional Optimization | **NOT STARTED** |
| **FAZA IV** | LIVE | **FORBIDDEN** until economic proof + explicit Owner approval |

Next operational action: `ACCUMULATE_NATURAL_BINDING_SKIP_GATE_OUTCOMES`.

---

## 14. What Must NOT Be Rebuilt

- Second parallel-paper daemon or LaunchAgent  
- Second FPC or accounting engine  
- Competing Decision Brain  
- V3 strategy stack  
- Live `core/trailing.py` overwrite for V2 experiments  
- PPG / 7D / score100 hard gates without new global proof  

---

## 15. Canonical document set

| Document | Role |
|----------|------|
| `TAE_CONSTITUTION.md` | Sole project-state SSOT (+ ARCHITECTURE_FREEZE) |
| `SESSION_START.md` | Sole session bootstrap |
| `PROJECT_BOOK.md` | This journal |
| `TAE_DEVELOPMENT_PROTOCOL.md` | Development process |
| `TAE_GIT_GOVERNANCE.md` | Git rules |

Sprint reports (`TAE_*.md`) are factual history — not competing constitutions.

---

## 16. Sprint history (recent)

| Sprint | Verdict |
|--------|---------|
| `TAE_FINAL_INFRASTRUCTURE_CLOSURE` | `TAE_INFRASTRUCTURE_CLOSED` |
| `V1_V2_CANONICAL_DUAL_STRATEGY_ACTIVATION` | `V1_V2_DUAL_STRATEGY_ACTIVE` |
| Economic loss / entry causality / global entry gate | Proven / identified |
| `BINDING_DECISION_BRAIN_SKIP_PAPER_GATE` | Gate ACTIVE in PAPER; cohort ACTIVE; permanence pending |
| `TAE_CANONICAL_DOCUMENTATION_CLOSURE` | Documentation closed |

---

*End of PROJECT BOOK — synced to Constitution v2.2*
