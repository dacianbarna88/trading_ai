# TAE Binding Decision Brain SKIP Paper Gate

**Sprint:** `BINDING_DECISION_BRAIN_SKIP_PAPER_GATE`  
**Mode:** PAPER_ONLY | NO_BROKER | NO_LIVE | NO_V3  
**Generated:** 2026-08-03  
**Prior proof:** `GLOBAL_ENTRY_GATE_PROVEN` (+$107.59 combined counterfactual)

## FINAL_VERDICT

**`BLOCKED_BY_PREEXISTING_FAILURE`**

Gate implementation, tests, attribution, isolation, and natural V2 OPEN blocks are green.  
Canonical `full-paper-cycle` remains **`BLOCKED_WITH_REASONS`** due to preexisting **`mark-to-market ALL_STALE with open positions`** (host mark freshness during orchestration). Standalone `paper-mark-to-market` marks 8/8 live with 0 stale — failure is FPC timing/mark pipeline, not the SKIP gate.

Gate code is **live in PAPER** (`DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED=true` default).  
Promote sprint verdict to `BINDING_DECISION_BRAIN_SKIP_PAPER_GATE_ACTIVE` only after FPC returns `READY_FOR_PAPER_DAY` / `READY_WITH_WARNINGS` without ALL_STALE.

---

## 1. Executive Summary

| Item | Result |
| --- | --- |
| Economic rule | Decision Brain canonical `SKIP` → block new PAPER entry |
| V1 BUY | Gate wired in `execute_decision` (NEW position only) |
| V2 OPEN | Gate wired in `evaluate_buy_policy` before `OPEN_CYCLE` |
| V2 ADD | Explicitly out of scope (`V2_ADD_NOT_IN_SCOPE`) |
| PPG / 7D / score100 | Not hard-gated |
| SELL / Hard Risk / trailing | Unchanged |
| Full suite | **193 OK** (4 skipped) |
| Natural blocks this run | V2 SPY OPEN ×3; V1 natural BUY+SKIP candidates = 0 |
| FPC | **BLOCKED** (ALL_STALE preexisting) |
| Commit | **NONE** (dirty working tree) |

---

## 2. Audit Before Patch

| COMPONENT | OWNER | FILE | FUNCTION | INPUT | OUTPUT | STATUS | ACTIVE | WIRED | PATCH_REQUIRED |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Decision Brain SKIP producer | PDE | `tae_paper_decision_engine.py` | `score_actions_for_ticker` → `build_decision` | scores/conflict/state | `action` ∈ PAPER_ACTIONS | EXISTS | YES | advisory | NO (consume) |
| Canonical field | PDE / memory | decision + `decisions.jsonl` | — | — | `SKIP_PAPER` / `BUY_PAPER` / `HOLD_PAPER` / … | EXISTS | YES | observe | NO |
| V1 payload | PDE→exec | `paper_decisions.json` | `action`, `previous_action` | — | may be BUY after override | EXISTS | YES | non-binding before | YES |
| V2 payload | parallel | `_run_v2_arm` | synthesized `pde_action` | signal/score | invented BUY over SKIP | GAP | YES | bypassed | YES |
| SKIP→BUY break | conflict + exec | `tae_conflict_resolution.py`, `should_execute_decision` | HIGH_RISK / action_changed | SKIP | BUY authorized | BREAK | YES | non-binding | YES (gate) |
| V1 authorize | paper exec | `tae_paper_execution.py` | `execute_decision` BUY branch | BUY_PAPER | fill | ACTIVE | YES | E3/noise only | YES |
| V2 authorize OPEN | buy policy | `tae_strategy_v2_buy_policy.py` | `evaluate_buy_policy` | BuyPolicyInput | OPEN_CYCLE | ACTIVE | YES | score≥80 bypass | YES |
| Dormant binding SKIP gate | — | — | — | — | — | MISSING | NO | NOT_WIRED | CREATE |
| E3 pattern (reuse) | paper exec | `evaluate_profit_decay_new_buy_gate` | env flag | NEW BUY | block | ACTIVE | YES | WIRED | REUSE PATTERN |

**SKIP owner:** Paper Decision Engine (`tae_paper_decision_engine.py`) via canonical field **`action`** (`SKIP_PAPER`). Longitudinal memory stores the same action for audit/SSOT lookup.

**Where obligation was lost:** conflict HIGH_RISK / STRONG BUY scoring and `action_changed:SKIP_PAPER->BUY_PAPER`; V2 synthesized `pde_action=BUY_PAPER` and score≥80 OPEN bypass.

---

## 3. Existing Decision Authority

Unchanged. Gate consumes Decision Brain / memory verdict — does not create a new authority, learning veto, or PPG/7D hard rule.

---

## 4. Root Cause (addressed)

Protective `SKIP_PAPER` was advisory. Binding PAPER entry gate now refuses NEW V1 BUY / V2 OPEN when canonical verdict resolves to SKIP.

---

## 5. Gate Policy

| Rule | Value |
| --- | --- |
| Flag | `DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED` (default `true`) |
| SSOT lookup | `DECISION_BRAIN_SKIP_GATE_SSOT_LOOKUP` (default `true`; tests set `false`) |
| Scope | PAPER, new V1 BUY, V2 OPEN only |
| Exit status | `BLOCKED_DECISION_BRAIN_SKIP` |
| Economic class | `ENTRY_BLOCKED_BY_DECISION_BRAIN_SKIP` |
| Out of scope | HOLD, SELL, STOP, CRITICAL, trailing, existing positions, V2 ADD, settlement, MTM, LIVE/broker |
| LIVE | always NO (`live_money` / broker / non-PAPER → not in scope) |

Resolution priority: explicit `decision_brain_verdict` → `action_changed:SKIP→…` → `previous_action` → latest other `paper_decisions` SKIP → longitudinal memory SKIP. Does not invent SKIP.

---

## 6. V1 Integration

In `execute_decision` BUY_PAPER path, after opening-noise + E3 gates, before fill:

1. `evaluate_decision_brain_skip_new_entry_gate(...)`  
2. On block: no cash/position mutation; terminal status; attribution event + forward cohort row.

---

## 7. V2 Integration

1. `_run_v2_arm` resolves real Decision Brain action (no longer invents BUY over SKIP).  
2. `evaluate_buy_policy` blocks `OPEN_CYCLE` when SKIP — returns `SKIP` + `BLOCKED_DECISION_BRAIN_SKIP` without creating a cycle.  
3. ADD path never enters this gate.

---

## 8. V1/V2 Isolation

| Check | Result |
| --- | --- |
| Separate portfolios | PASS |
| strategy_id on block events | V1 / V2 |
| V1 block does not mutate V2 cash | PASS (unit) |
| No cross-strategy dedup | PASS |
| Same ticker different verdicts possible | by design (per-strategy resolve + strategy_id) |

---

## 9. Attribution

Canonical journal: `runtime_outputs/paper_execution/decision_brain_skip_blocks.jsonl`  
Forward cohort: `runtime_outputs/paper_execution/binding_skip_gate_forward_cohort.jsonl` (`BINDING_SKIP_GATE_FORWARD_COHORT`, status PENDING)

Fields include: strategy_id, ticker, timestamp, decision_id, orchestration_run_id (when present), original/final action, Decision Brain verdict/source, gate name, block reason, score/confidence, PPG/forecast/regime/learning when present, blocked price, counterfactual class.

---

## 10. Learning Provenance

Learning algorithm unchanged (`TESTING` / `influence_delta` may remain 0). Gate consumes canonical SKIP verdict only — not annotations, PPG, or 7D alone.

Chain after patch:

```
Learning → Decision Delta (still soft)
        → Decision Brain SKIP (canonical)
        → Binding PAPER entry gate  ← NEW hard stop for NEW BUY/OPEN
        → (no fill)
```

---

## 11. Files / Functions Changed

| File | Change |
| --- | --- |
| `tae_paper_execution.py` | Flag, resolve, evaluate, append, BUY wiring, terminal status, order attribution fields |
| `tae_strategy_v2_buy_policy.py` | OPEN-only binding gate before cycle create |
| `tae_parallel_paper_runtime.py` | Real Decision Brain `pde_action`; reentry OPEN uses same |
| `tae_test_isolation.py` | Hermetic `DECISION_BRAIN_SKIP_GATE_SSOT_LOOKUP=false` |
| `tae_decision_brain_skip_gate_test.py` | NEW mandatory tests |

No Hard Risk / SELL / trailing / sizing / core/ / broker / daemon / LaunchAgent / scheduler changes.

---

## 12. Tests

`python3 tae.py test` → **193 discovered, 0 failures, 4 skipped, ok=True**

Covered: V1 SKIP block, V1 BUY/HOLD allow, V2 OPEN SKIP block, V2 OPEN BUY allow, V2 ADD unaffected, SELL unchanged, existing position not NEW-gated, cash unchanged, terminal idempotency, flag off, isolation, LIVE out of scope, deterministic reason codes.

---

## 13. PAPER Validation

| Check | Result |
| --- | --- |
| health | PASS (READY_WITH_WARNINGS — dirty tree) |
| full-paper-cycle ×3 | **BLOCKED_WITH_REASONS** — ALL_STALE (preexisting) |
| paper-mark-to-market alone | PASS (8 live / 0 stale) |
| Natural V2 OPEN SKIP blocks | **3** (SPY) |
| Natural V1 BUY SKIP blocks | **0** (`NO_NATURAL_SKIP_ENTRY_CANDIDATE` for V1 this run) |
| Accounting isolation | cash books unchanged by blocks |

---

## 14. Baseline

Captured: `runtime_outputs/paper_execution/binding_skip_gate_baseline.json`

| | Before | After |
| --- | ---: | ---: |
| V1 equity | 29729.3175 | 29734.2703 |
| V2 equity | 29884.950422 | 29897.050232 |
| V1 cash | 21235.7828 | 21235.7828 |
| V2 cash | 24952.3243 | 24952.3243 |

Equity deltas are MTM/mark movement, not SKIP-gate fills (blocks prevent cash mutation).

---

## 15. Forward Cohort

- Owner: `runtime_outputs/paper_execution/binding_skip_gate_forward_cohort.jsonl`  
- Status: **ACTIVE** (rows PENDING outcomes)  
- Do not declare profitability this sprint.

---

## 16. Economic Validation Gates (forward)

Remain after ≥10 total blocks, ≥5/strategy when natural, ≥5 mature outcomes:

net avoided PnL, missed winner PnL, HR rate change, expectancy/ROI change, opportunity cost, capital utilization.

---

## 17. Rollback Conditions

PAPER rollback (manual): `DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED=false`

Stop / consider rollback if: missed profit > avoided loss; material V1 harm; V2 HR not improved; attribution incomplete; cross-strategy contamination; accounting fail; FPC fail attributable to gate.

This sprint: **no automatic rollback** (technical gate healthy; FPC ALL_STALE preexisting).

---

## 18. Limitations

- Small historical n from prior audit; forward cohort immature.  
- V1 absolute counterfactual was ~flat; quality/HR improvement still desired.  
- FPC ALL_STALE prevents formal ACTIVE sprint verdict.  
- V2 ADD not gated (explicit).  
- SSOT memory lookup disabled in unit isolation by design.

---

## 19. Final Verdict

**`BLOCKED_BY_PREEXISTING_FAILURE`**

Preexisting failure: FPC `mark-to-market ALL_STALE with open positions`.

**NEXT_ACTION=`ACCUMULATE_NATURAL_BINDING_SKIP_GATE_OUTCOMES`** (and clear FPC ALL_STALE to promote verdict).
