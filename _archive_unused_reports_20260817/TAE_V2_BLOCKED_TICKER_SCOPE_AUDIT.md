# TAE V2 BLOCKED_TICKER_SCOPE Audit

**Mode:** READ ONLY — no code/runtime/PAPER mutation, no commit.
**HEAD:** `fb584243a4a9453df38c0620e7d8cf16efd0b3d8`
**Generated:** `2026-07-29T23:50:53.465793+00:00`

## Verdict

**`SCOPE_BLOCK_IS_RUNTIME_POLICY_INCONSISTENCY`**

Adaptive Deployment canary ticker whitelist is a **legitimate challenger limiter**, but on 29 Jul it was applied as a **hard veto of an already V2-authorized ADD** on an open GE cycle. That conflicts with V2 price-driven ADD and with the canary’s original “no V2 tranche switching” intent / USE_CONTROL pattern.

## Central answer

**No — it is not correct** for ADD on an already-open V2 cycle to be hard-blocked solely because the ticker is outside the *challenger canary* whitelist, while V2 buy policy already returned `ADD_TRANCHE` (`V2_TRANCHE_ALLOWED`).

Scope should gate **challenger sizing**, not erase **control-path accumulation** on grandfathered cycles.

## What BLOCKED_TICKER_SCOPE is

| Field | Value |
|---|---|
| Authority | Adaptive Deployment SSOT (PAPER canary) |
| Source | `runtime_outputs/adaptive_deployment/deployment_state.json field ticker_scope` |
| Current scope | `['AAPL', 'MSFT', 'NVDA']` |
| Entry scope @ Jul29 ADD | `NEW_BUY_AND_ELIGIBLE_V2_ADD (migrated 2026-07-28T18:45:48Z)` |
| Purpose | Limit PAPER_CHALLENGER sizing experiment to a small ticker whitelist (AAPL,MSFT,NVDA); FAIL_CLOSED_TO_NO_NEW_BUY for out-of-scope NEW buys on the challenger path. |

Not a V1 strategy universe, not exchange/region/FX validation, not replay-only.

## Path (Parallel V2)

```
mark → V2 exit/manage → evaluate_buy_policy (ADD_TRANCHE)
    → _apply_adaptive_deployment_to_v2_buy
    → resolve_buy_notional(arm=V2)
    → ticker_in_scope? GE ∉ {AAPL,MSFT,NVDA} → BLOCKED_TICKER_SCOPE
    → ADD aborted (no fill)
```

Order bug / semantic conflict: `ticker_scope` hard-block runs **before** V2 `entry_scope` USE_CONTROL branch.

## GE reconstruction

| Item | Value |
|---|---|
| Cycle | `V2CYC-GE-DFA94F8432D3` |
| OPEN | 2026-07-27T13:54:50Z @ 362.08 qty 1.38091 (~$500) — **before** canary |
| OPEN scope check | canary inactive (DRAFT) → passed |
| ADD eval | 2026-07-29T16:16:34Z px 350.44 drop 3.215% |
| V2 policy | `V2_TRANCHE_ALLOWED` / ADD eligible |
| Scope at ADD | **blocked** |
| Executed | **no** (4 re-evals same day) |

Canary activated `2026-07-28T18:25:15Z`; entry_scope migrated to include V2 ADD `2026-07-28T18:45:48Z` — both **after OPEN**, before the missed ADD.

Classification OPEN vs ADD: **E** (ADD uses adaptive scope) + **G** (hard-block instead of control fallback). Not symbol normalization.

## Surfaces

| Surface | Blocks ADD? | Notes |
|---|---|---|
| V2 stateful replay | No | no adaptive hook |
| Parallel V2 runtime | **Yes** | real Jul29 journal |
| Parallel V1 | Yes (new buys) | GE/SIE.DE entry blocks |
| Canonical PAPER | Wired | 0 `BLOCKED_TICKER_SCOPE` in `paper_orders.jsonl` observed |
| LIVE | No | `live_allowed=false`; no LIVE call sites |

## History

- V2 parallel scope blocks: **4** (all GE ADD re-evals Jul29)
- OPEN allowed → ADD scope blocked cycles: **1** (GE)
- Missed ADD capital: **$500**
- Counterfactual PnL effect (GE ADD vs blocked): **+5.471462 USD** on that day (policy_only − primary)

## Risk

- Safety value of scope: **MEDIUM** (canary containment)
- If removed entirely: Canary could size challenger on any ticker; capital_limit still caps exposure but experiment contamination rises
- If kept as hard ADD veto: Continues vetoing control-path V2 ADDs on grandfathered open cycles outside whitelist (missed accumulation)

Safe policy: whitelist gates challenger only; out-of-scope V2 ADD → **control fallback**.

## Recommendation (not applied)

1) In resolve_buy_notional: evaluate entry_scope for V2 before ticker_scope hard-block, OR on ticker out-of-scope return USE_CONTROL instead of blocked for arm=V2. 2) In _apply_adaptive_deployment_to_v2_buy: treat BLOCKED_TICKER_SCOPE as non-fatal → proceed with control proposed_tranche_value. 3) Add tests: open cycle GE + whitelist AAPL-only + ADD threshold → ADD executes on control.

Files:
- `tae_adaptive_deployment.py`
- `tae_parallel_paper_runtime.py`
- `tae_adaptive_deployment_test.py`
- `tae_parallel_paper_test.py`

## Explicit output block

```
HEAD=fb584243a4a9453df38c0620e7d8cf16efd0b3d8
WORKTREE_STATUS=DIRTY
AUDIT_MODE=READ_ONLY
TARGET_REASON=BLOCKED_TICKER_SCOPE
FINAL_VERDICT=SCOPE_BLOCK_IS_RUNTIME_POLICY_INCONSISTENCY
```
