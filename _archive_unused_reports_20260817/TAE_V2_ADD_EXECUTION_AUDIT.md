# TAE V2 ADD Execution Audit (Parallel PAPER)

**Date:** 2026-07-29  
**HEAD:** `11e4adb13ffe3aadb2f0214e86769c3284c893eb`  
**Scope:** V2 Parallel PAPER only · READ-ONLY cause analysis · **NO_CODE_CHANGE**  
**Companion:** `tae_v2_add_execution_audit.json`

---

## Executive verdict

**`V2_ADD_METRIC_WAS_INCORRECT`**

The prior count `PRICE_REACHED_ADD_THRESHOLD=9` counted marks ≤ last×0.97 on cycles that were already **`ACCUMULATION_STOPPED`** (reason journaled as `V2_HOLD_OPEN`). Those are **not** ADD-eligible.

After contemporaneous reconstruction:

| Metric | Value |
|--------|------:|
| Raw mark≤threshold events (any open-like status) | 20 |
| Of which `ACCUMULATION_STOPPED` / not ADD-eligible | 18 |
| **True hits while status ∈ {OPEN, ACCUMULATING}** | **2** |
| Those 2 final decisions | **`HOLD` / `HOLD_THESIS_WATCH`** (score 60, thesis WATCH) |
| `ADD_TRANCHE` emitted / executed historically | **0** |

Decision→execution for ADD is **connected and works** when policy emits `ADD_TRANCHE` (proven by existing unit tests + synthetic temp-dir OPEN→ADD2→ADD3). No repair commit.

---

## Phase 1 — Runtime / owners

| Action | Policy | Runtime | Persist |
|--------|--------|---------|---------|
| OPEN_CYCLE | `evaluate_buy_policy` | `_run_v2_arm` → `execute_decision(..., override=True)` | `apply_open_or_add_tranche` |
| ADD_TRANCHE | same + profit gate | same after exit HOLD when `allow_add` | same; **requires** status ∈ `{OPEN,ACCUMULATING}` |
| HOLD | buy/exit | journal HOLD / `V2_HOLD_OPEN` | no capital mute |
| STOP_ACCUMULATION | buy or exit | `apply_stop_accumulation` | status → `ACCUMULATION_STOPPED` |
| CLOSE_CYCLE | `evaluate_exit_policy` | `_sell_shares` path | CLOSED |

`ADD_ALLOWED = {OPEN, ACCUMULATING}` (`tae_strategy_v2_foundation`). Preflight **rejects** ADD if `ACCUMULATION_STOPPED` (`BLOCK_INVALID_CYCLE`).

---

## Phase 2 — CASE_1 … CASE_9 (prior metric rows)

These are the **exact 9** prior-audit rows (`reason=V2_HOLD_OPEN` ∧ mark≤last×0.97 using cycle last price).

| Case | ts (UTC) | ticker | cycle_id | mark | last_buy | threshold | drop% | status @ event | final | rejection |
|------|----------|--------|----------|------|----------|-----------|------:|----------------|-------|-----------|
| 1 | 2026-07-28T13:54:29Z | SIE.DE | V2CYC-SIE.DE-389D4B98B341 | 268.50 | 276.85 | 268.5445 | 3.02% | ACCUMULATION_STOPPED | HOLD | not ADD-eligible (stopped 2026-07-27T22:09:21Z `STOP_INVALID_DATA`) |
| 2 | 2026-07-28T14:00:14Z | SIE.DE | same | 268.40 | 276.85 | 268.5445 | 3.05% | ACCUMULATION_STOPPED | HOLD | same |
| 3 | 2026-07-28T14:11:30Z | SIE.DE | same | 268.45 | 276.85 | 268.5445 | 3.03% | ACCUMULATION_STOPPED | HOLD | same |
| 4 | 2026-07-29T13:32:22Z | PG | V2CYC-PG-D7241E308784 | 143.24 | 148.56 | 144.1032 | 3.58% | ACCUMULATION_STOPPED | HOLD | same freeze |
| 5 | 2026-07-29T13:37:52Z | PG | same | 143.27 | 148.56 | 144.1032 | 3.56% | ACCUMULATION_STOPPED | HOLD | same |
| 6 | 2026-07-29T16:16:34Z | GE | V2CYC-GE-DFA94F8432D3 | 350.44 | 362.08 | 351.2176 | 3.21% | ACCUMULATION_STOPPED | HOLD | same |
| 7 | 2026-07-29T16:22:02Z | GE | same | 350.42 | 362.08 | 351.2176 | 3.22% | ACCUMULATION_STOPPED | HOLD | same |
| 8 | 2026-07-29T16:27:27Z | GE | same | 350.85 | 362.08 | 351.2176 | 3.10% | ACCUMULATION_STOPPED | HOLD | same |
| 9 | 2026-07-29T16:38:11Z | GE | same | 351.08 | 362.08 | 351.2176 | 3.04% | ACCUMULATION_STOPPED | HOLD | same |

Common fields for all nine:

```text
configured_add_threshold=0.03
reference_price_used=last_tranche_price (SSOT)
current_tranche_count=1
execution_attempted=false
execution_result=n/a
state_changed=false
accounting_changed=false
hard_risk_status=not the blocking reason (path short-circuits via stopped / V2_HOLD_OPEN)
```

### True ADD-eligible threshold hits (not in the “9”)

| ts | ticker | mark | last | drop% | decision | reason |
|----|--------|------|------|------:|----------|--------|
| 2026-07-27T13:37:42Z | NVDA | 205.63 | 212.56 | 3.26% | HOLD | **HOLD_THESIS_WATCH** (score=60 → thesis WATCH) |
| 2026-07-27T13:43:11Z | NVDA | 203.38 | 212.56 | 4.32% | HOLD | **HOLD_THESIS_WATCH** |
| → 13:49:27Z | NVDA | 201.51 | | | CLOSE | CLOSE_HARD_RISK_CRITICAL (−5% path) |

Policy correctly refuses ADD without thesis VALID (score≥80 or favorable PDE). Minutes later critical hard-risk closed the cycle — never an unexecuted ADD_TRANCHE.

---

## Phase 3 — Threshold / reference

| Param | Effective |
|-------|-----------|
| BUDGET_PER_TICKER | 500–2500 (`minimum_company_budget` / `maximum_company_budget`) |
| TRANCHE_FRACTION | 0.20 |
| TRANCHE_VALUE | budget×0.20 (min order 250) |
| MAX_TRANCHES | 5 |
| ADD_DROP_THRESHOLD | **0.03** |
| ADD_REFERENCE_TYPE | **`last_tranche_price`** |
| CRITICAL_HARD_RISK | −5% (adapter); −3% = V1-only class |
| EXIT_TARGET | +10% cycle / V2 trailing +5/−2 |

Reference updates on each successful OPEN/ADD fill (`next_tranche_reference_price` / `last_tranche_price` in foundation). Persists in `cycle_state.json`. After `apply_stop_accumulation`, ADD preflight fails regardless of price.

---

## Phase 4 — Funnel (journal scan @ audit time)

```text
TOTAL_REEVALUATIONS                 5745
ACTIVE_CYCLE_REEVALUATIONS          5477
PRICE_BELOW_REFERENCE               2380
PRICE_REACHED_ADD_THRESHOLD_RAW       20   ← naive metric
PRICE_REACHED_WHILE_ADD_ELIGIBLE       2   ← corrected
  └─ HOLD_THESIS_WATCH                 2
STOPPED_HITS (not eligible)           18
  └─ V2_HOLD_OPEN                      9   ← prior "9"
  └─ HOLD_THESIS_WATCH                 5
  └─ BLOCKED_TICKER_SCOPE              4
CYCLE_OPEN / TRANCHE_LIMIT / BUDGET / CASH / …  (not binding on the 2 true hits)
VALID_FOR_ADD                          0   (price+status+thesis+signal)
ADD_DECISION_EMITTED                   0
ADD_AUTHORIZED                         0
EXECUTION_ATTEMPTED                    0
FILL_CREATED                           0
ADD_EXECUTED                           0
```

Dominant non-ADD reasons on open cycles: `HOLD_PRICE_STEP_NOT_REACHED`, `V2_HOLD_OPEN` (post-stop), `HOLD_THESIS_WATCH`. Mass `STOP_INVALID_DATA` at 2026-07-27T22:09:21Z froze 12 cycles before most later “hits”.

---

## Phase 5 — Decision→execution

```text
evaluate_buy_policy → materialize_v2_execution_decision → execute_decision
  → execute_strategy_v2_decision → preflight → apply_open_or_add_tranche
  → tranche_events.jsonl + cycle_state + portfolio cash/qty
```

| Failure mode checked | Result |
|----------------------|--------|
| ADD generated but not consumed | **No historical ADD generated** |
| Router missing ADD | **False** — `_run_v2_arm` handles `bact==ADD_TRANCHE` |
| ACCUMULATION_STOPPED still ADD | Preflight blocks (correct) |
| Qty→0 / min notional | Not reached historically |
| Synthetic path | OPEN+ADD2+ADD3 EXECUTED in temp dir |

---

## Phase 6–7 — Ordering / market data

Exit evaluation runs before ADD (`allow_add` after protective exit). `V2_HOLD_OPEN` is the post-exit hold when ADD not taken. NVDA marks were live session prices; thesis WATCH from **score 60**, not FX/stale artifact. STOP_INVALID_DATA batch at 22:09Z is mark/data validity stop (permanent accumulation freeze) — separate from the “9”.

---

## Phase 8 — Cause classification

```text
OBSERVATION_METRIC_INCORRECT     ← primary (prior "9")
ADD_POLICY_CORRECTLY_REJECTED    ← 2 true hits (HOLD_THESIS_WATCH)
ADD_REFERENCE_PRICE_BUG          ← not demonstrated
DECISION_NOT_ROUTED_TO_EXECUTION ← not demonstrated
```

---

## Phase 9 — Correction

**None.** Do not change thresholds, do not force ADD, do not enable `STRATEGY_V2_ENABLED`.

Optional future observation (out of scope): whether `STOP_INVALID_DATA` → permanent `ACCUMULATION_STOPPED` is too aggressive vs temporary HOLD — **not** required to explain the “9”.

---

## Phase 10 — Tests / synthetic

Ran: foundation + buy_policy + exit_policy + parallel_paper + v1/v2 isolation → **126 OK**.

Synthetic (temp dir, isolated capital):

```text
OPEN_EXECUTED=1
ADD_2_EXECUTED=1  (price 97)
ADD_3_EXECUTED=1  (price 94.09)
DUPLICATE_ADDS=0
TRANCHE_COUNT=3
BUDGET_CONSERVED=PASS
CASH_CONSERVED=PASS
STATE_PERSISTENCE=PASS
```

Historical replay with unchanged code: the prior 9 still would **not** ADD; the 2 NVDA hits still **HOLD_THESIS_WATCH**.

---

## Final

```text
FINAL_VERDICT=V2_ADD_METRIC_WAS_INCORRECT
CODE_CHANGE_REQUIRED=false
NO_COMMIT=true
```
