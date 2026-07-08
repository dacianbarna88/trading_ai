# TAE Main Decision Brain Closure Audit

**Generated:** 2026-07-08T19:50:00+00:00  
**Branch:** `cursor/x12b-legacy-archive-hotfix`  
**Base commits:** `59982ee` (decision state wiring) · `d39ec35` (PAPER stabilization)  
**Mode:** PAPER_ONLY · ADVISORY_ONLY · NO_BROKER · NO_MASTER_DECISION_AUTHORITY  
**Final verdict:** **MAIN_DECISION_BRAIN_CLOSED**

---

## Executive summary

The TAE main PAPER decision brain is **closed**: a single traceable final action per ticker is produced by **`tae_paper_decision_engine.py` (PDE)**, gated by hard risk first, decision state, and conflict-resolution evidence, then consumed by execution, accounting, and longitudinal memory without duplicate decision engines.

No new modules were created. One minimal test-alignment patch was applied (stale unit tests after 59982ee).

---

## End-to-end decision path

```
[1] Data / market inputs
    build_context() — GII, live_signals.csv, paper_portfolio, APPE/PPG, DPE, LTP, historical SSOT
         ↓
[2] Hard Risk Guardian (ALWAYS FIRST)
    enforce_hard_risk_discipline() — hard_risk.json → early SELL_PAPER override
         ↓
[3] PDE scoring layers
    position_discipline → loss_discipline → policy/protection/knowledge/weights
         ↓
[4] Conflict Resolution (evidence bias — NOT final authority)
    apply_conflict_resolution_bias() — EV scenario boost; precomputed conflicts.json
         ↓
[5] Decision State Gate (anti-churn owner)
    apply_decision_state_gate() — switch auth, cooldown, STOP_REENTRY_CHURN
         ↓
[6] Final action object
    build_decision() → paper_decisions.json / paper_decisions.jsonl
    ONE row per ticker · decision_id · decision_switch_authorized · hard_rule_override
         ↓
[7] Paper Execution
    should_execute_decision() + switch auth check → EXECUTED | SKIPPED_SWITCH_NOT_AUTHORIZED
         ↓
[8] Paper Accounting
    paper_portfolio.json — mutates ONLY on executed=true orders
         ↓
[9] Longitudinal Memory
    ingest_decisions() — ACTION_CHANGE events on same decision_id
```

**Orchestrator:** `tae_structural_governance.py` → `python3 tae.py full-paper-cycle`

---

## Audit questions answered

| Question | Answer | Evidence |
| --- | --- | --- |
| Where is single final action selected? | **PDE `build_decision()`** after hard risk + state gate | `tae_paper_decision_engine.py` |
| One final decision per ticker per cycle? | **Yes** — 25 tickers → 25 unique decision_ids | `paper_decisions.json` |
| decision_id stable & traceable? | **Yes per ticker** — `PDEC-{TICKER}-{seq:04d}` from sorted universe | e.g. `PDEC-AMAT-0005` |
| One active owner per ticker? | **Yes** — `active_decisions.json` + stable decision_id | `tae_decision_state.py` |
| PDE vs Conflict Resolution disagree after finalization? | **No** — conflict is score bias only; PDE owns final action | No post-PDE conflict override |
| Execution mutates without authorization? | **No** — `SKIPPED_SWITCH_NOT_AUTHORIZED` blocks | 3 skips latest cycle |
| action_changed bypass switch auth? | **No** — requires `decision_switch_authorized` or hard override | `tae_paper_execution.py` |
| Unauthorized BUY→SELL→BUY execute? | **No on policy tickers** — AIR.PA/DIA/GE blocked | HOLD + skip |
| STOP_REENTRY_CHURN bypassed? | **Only via strong EV exception** — cooldown enforced | AMAT/HD/MU cooldown active |
| Hard -3% SELL bypasses soft gates? | **Yes** — `hard_risk_discipline.override` | AMAT SELL when breach active |
| ACTION_CHANGE without silent skip? | **Yes** — 27 events in memory records | `longitudinal_memory/decisions.jsonl` |
| Blocked decisions visible in reports? | **Yes** — switch blocked counts in 5 reports | PDE/cycle/council/conflict/state |
| Canonical runtime paths? | **Yes** — single SSOT under `runtime_outputs/` | No duplicate writers |

---

## What is NOT the decision brain

| Module | Role |
| --- | --- |
| `tae_conflict_resolution.py` | EV evidence orchestrator — biases PDE scores |
| `tae_decision_state.py` | State builder + switch gate — not a decision engine |
| `tae_decision_governor.py` | Legacy SHADOW VIEW — not connected to PAPER cycle |
| Investment Council | Synthesis report only — no execution authority |
| DPE competitive/collaborative | Isolated learning portfolios — not main PAPER brain |

---

## Validation (Phase 4)

```bash
python3 tae.py decision-state-refresh
python3 tae.py full-paper-cycle
python3 tae.py decision-state-refresh
python3 tae.py full-paper-cycle
python3 tae.py full-paper-cycle
python3 -m unittest tae_decision_state_test tae_conflict_resolution_test \
  tae_paper_execution_test tae_longitudinal_outcome_memory_test tae_paper_decision_engine_test
git diff -- live_bot.py portfolio.csv live_signals.csv watchlist.txt core/ research_core/
```

| Check | Result |
| --- | --- |
| Governance verdict | **READY_FOR_PAPER_DAY** |
| Reconciliation | **PASS** |
| Forbidden paths diff | **0** |
| Promotion lock | **false** |
| Unauthorized executed switches | **0** |
| Blocked switches logged | **3** (AIR.PA, DIA, GE) |
| Unit tests | **45/45 PASS** |

---

## Code patch (minimal — test alignment only)

| File | Change | Justification |
| --- | --- | --- |
| `tae_paper_decision_engine_test.py` | Unpack 10-tuple from `score_actions_for_ticker` | Signature changed in 59982ee (added `hard_risk_discipline`) |
| `tae_paper_execution_test.py` | Add `decision_switch_authorized: true` to reexecute test | Execution gate requires auth since 59982ee |

**No production code patched** — brain wiring complete from prior commits.

---

## Known limitations (not defects)

1. **decision_id seq** is index in sorted ticker universe — stable while membership stable; new tickers alphabetically before a symbol could shift its seq.
2. **Rapid multi-cycle runs** exercise authorized high-EV switches (AMAT/HD) — run once per session for disciplined PAPER.
3. **Hard -3% override** clears after position flat until next breach.

---

## Operational rule

```bash
python3 tae.py full-paper-cycle   # once per market session
```

Expect: `READY_FOR_PAPER_DAY` · reconciliation `PASS` · `live_promotion_allowed=false`

---

## Next allowed work

- **30-day disciplined PAPER validation** — daily cycle, track reports
- **Read-only audits** — no new decision engines
- **NOT allowed:** Master Decision Authority, live broker, live promotion unlock

---

## Machine-readable companion

`tae_main_decision_brain_closure_audit.json`
