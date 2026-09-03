# TAE V2 OPEN vs ADD Policy Audit (READ-ONLY)

**Date:** 2026-07-29  
**HEAD:** `11e4adb13ffe3aadb2f0214e86769c3284c893eb`  
**Scope:** Parallel PAPER V2 economic coherence only · NO_CODE_CHANGE · NO_COMMIT  
**Companion:** `tae_v2_open_vs_add_policy_audit.json`

---

## Executive answer

OPEN and ADD use the **same** thesis authority (`classify_thesis`) and the **same** score bar (`score ≥ 80` **or** favorable PDE ∈ `{BUY_PAPER,BUY,STRONG_BUY}`).

For **NVDA** (the only ticker with true price-threshold hits while OPEN):

| Moment | score | thesis | decision |
|--------|------:|--------|----------|
| OPEN 2026-07-23T16:53:04Z | **100** | VALID | OPEN_CYCLE |
| ADD hit #1 2026-07-27T13:37:42Z | **60** | WATCH | HOLD_THESIS_WATCH |
| ADD hit #2 2026-07-27T13:43:11Z | **60** | WATCH | HOLD_THESIS_WATCH |

Score had already left the ≥80 band on **2026-07-24T21:23:13Z** (score **40**, mark **215.0** — *above* entry). So WATCH was **not** created by the −3% ADD print; it reflected a **prior signal deterioration**. When price later reached the ADD step, thesis was still WATCH → ADD correctly blocked.

**Historical fully-eligible ADD windows (OPEN ∧ thesis VALID ∧ drop≥3%): `0`.**

**Verdict:** `THESIS_CORRECTLY_DETERIORATED_AFTER_OPEN`  
(also: `WATCH_CORRECTLY_BLOCKS_ACCUMULATION`; self-blocking price→WATCH loop **not** formula-proven).

---

## Phase 1 — Authorities

| Concern | FILE | FUNCTION | Key thresholds | Next |
|---------|------|----------|----------------|------|
| Market snap score/eligible | `tae_parallel_paper_runtime.py` | signal/mark builder (~790–821) | eligible if Signal BUY/STRONG BUY **or** score≥80 | `_run_v2_arm` |
| PDE proxy | `_run_v2_arm` (~2277–2280) | `pde_action = BUY_PAPER if favorable else HOLD_PAPER` | same favorable rule | BuyPolicyInput |
| Thesis SSOT | `tae_strategy_v2_buy_policy.py` | **`classify_thesis`** | VALID iff favorable ∧ eligible≠False ∧ mark_ok | `evaluate_buy_policy` |
| OPEN / ADD / HOLD_THESIS_WATCH | same | **`evaluate_buy_policy`** | ADD also needs last×(1−0.03); WATCH→HOLD before price check | `_run_v2_arm` |
| Cycle status | `tae_strategy_v2_foundation.py` | `apply_stop_accumulation` etc. | ADD_ALLOWED={OPEN,ACCUMULATING} | preflight |
| Exit / critical | `tae_strategy_v2_exit_policy.py` + hard_risk adapter | −5% critical close | closes cycle | execution |

**OPEN and ADD use the same thesis function and same score/PDE thresholds.** Difference: ADD additionally requires price step; WATCH short-circuits **before** the price-step check.

---

## Phase 2 — True hits (NVDA only)

### TRUE_HIT shared OPEN baseline

```text
timestamp_open          = 2026-07-23T16:53:04Z
ticker                  = NVDA
cycle_id                = V2CYC-NVDA-C873797D0E9B
market_price / entry    = 212.56
entry_score             = 100.0
minimum_entry_score     = 80.0   (classify_thesis / snap eligible)
confidence              = not journaled as separate field (score used)
thesis_state            = VALID
risk/regime/fundamentals/technicals (as separate SSOT) = not stored on decision;
                          score/signal from signals.csv|live_signals.csv snap
decision                = OPEN / OPEN_VALID_CANDIDATE
company_budget          = 2500.0
tranche_value           = 500.0 (filled 499.999999)
```

### TRUE_HIT_1 — ADD threshold

```text
timestamp               = 2026-07-27T13:37:42Z
last_tranche_price      = 212.56
current_price           = 205.63
drop_pct                = 3.260%
required_drop_pct       = 3.0%
tranche_count           = 1
budget_remaining        = ~2000
entry_score_now         = 60.0
thesis_state_now        = WATCH
mark_status             = FRESH
ADD eligibility         = FAIL (thesis)
final_decision/reason   = HOLD / HOLD_THESIS_WATCH
executor_called         = false
```

| Variable | OPEN | ADD hit 1 | Δ | Threshold | Pass OPEN | Pass ADD |
|----------|------|-----------|---|-----------|-----------|----------|
| score | 100 | 60 | −40 | ≥80 | YES | **NO** |
| thesis | VALID | WATCH | — | VALID for ADD path | YES | **NO** |
| mark | 212.56 | 205.63 | −3.26% | ≤206.1832 for step | n/a | YES (price) |
| mark_fresh | (open fill) | FRESH | — | FRESH | YES | YES |

**FAILED_CONDITION:** `score >= 80` (distance **+20**).  
Price step alone would pass.

### TRUE_HIT_2 — ADD threshold

```text
timestamp               = 2026-07-27T13:43:11Z
current_price           = 203.38
drop_pct                = 4.319%
score                   = 60.0
thesis                  = WATCH
final                   = HOLD / HOLD_THESIS_WATCH
```

Same failed condition; distance **+20** score points.

Score path before hits:

```text
2026-07-23 OPEN     score=100 VALID
2026-07-24T21:23:13 score=40  WATCH  mark=215.0  (! still above entry)
2026-07-27T12:00:40 score=60  WATCH  mark=206.84
… hits at 13:37 / 13:43 still score=60
2026-07-27T13:49:27 CLOSE_HARD_RISK_CRITICAL mark=201.51
```

---

## Phase 3 — Exact WATCH production

```text
FILE:     tae_strategy_v2_buy_policy.py
FUNCTION: classify_thesis

raw inputs @ hit:
  score=60.0
  pde_action = HOLD_PAPER   # runtime: favorable=False when score<80
  candidate_eligible = from snap (score≥80 or BUY signal) → false/not favorable path
  cycle present = True
  mark_ok = True (FRESH)
  hard_risk_active = False (else INVALID/exit)

formula:
  favorable = (pde in {BUY_PAPER,BUY,STRONG_BUY,STRONG BUY})
              OR (score is not None AND score >= 80)
  if favorable and eligible is not False and mark_ok:
      → VALID
  elif (eligible is True OR held OR cycle) and mark_ok:
      → WATCH , reason REASON_HOLD_WATCH (= HOLD_THESIS_WATCH)

comparison @ hit:
  favorable = False   (60 < 80, pde HOLD_PAPER)
  cycle     = True
  → WATCH

then evaluate_buy_policy:
  if thesis == "WATCH": return HOLD / HOLD_THESIS_WATCH
  (price_drop_reached never evaluated on this branch)
```

**Cause class:** **score decrease** (signal snap), not stale data, not missing history, not default-unknown. Not a pure function of the −3% print (score fell earlier while price was still up).

---

## Phase 4 — OPEN vs ADD rule table

| RULE | OPEN_CYCLE | ADD_TRANCHE | SAME? | Note |
|------|------------|-------------|-------|------|
| entry score ≥80 or BUY PDE | required for VALID | required for VALID | **SAME** | |
| thesis VALID | required | required | **SAME** | WATCH blocks both new OPEN and ADD |
| confidence separate | not a second gate | not a second gate | SAME | score doubles as signal |
| risk regime / PCE gate | OPEN: light; ADD: extra profit-context gate after VALID | DIFFERENT after VALID | ADD has tranche profit gate |
| price decline | not required | **required −3% vs last tranche** | **DIFFERENT** | core ADD economic rule |
| hard risk | blocks | blocks / −5% closes | SAME family | |
| budget/cash | required | required | SAME family | |
| cycle state | none | OPEN/ACCUMULATING | ADD-only | |

**Can OPEN be allowed when ADD would already be impossible on the same data?**  
On the **same** score/PDE/eligibility snapshot: if score≥80 → both thesis-VALID; ADD still needs the price step (absent at first fill). If score&lt;80 → OPEN also denied (WATCH/not OPEN). So no “OPEN with score that can never ADD on thesis alone.”

**State allowed at OPEN but forbidden at ADD:** none for thesis bar. ADD adds **price-step** and (later) **profit-context gate** and **ADD_ALLOWED status**.

---

## Phase 5 — Persist vs reevaluate

```text
Intended/effective model = B
  Thesis is fully reclassified each reevaluation from live snap score/PDE.
  cycle.thesis_state may remain "VALID" on disk after OPEN but is NOT the ADD gate.
  THESIS_SNAPSHOT_PERSISTED = stored on cycle, not authoritative for ADD
  THESIS_REEVALUATED_EACH_CYCLE = true

WATCH = temporary HOLD of accumulation (reversible if score/PDE become favorable again)
ACCUMULATION_STOPPED = separate permanent freeze until new cycle (STOP_INVALID_DATA etc.)
  — not what blocked the 2 hits
```

---

## Phase 6 — Contradiction test

Policy does **not** compute score from the price drop. Score is imported from `signals.csv` / `live_signals.csv`.

For NVDA, WATCH began while **mark ≥ entry**. Therefore:

```text
PRICE_DROP_DEGRADES_TECHNICAL_SCORE = not demonstrated in-engine
PRICE_DROP_CAN_CAUSE_WATCH = not as a direct formula
WATCH_BLOCKS_ADD = true
SELF_BLOCKING_LOOP_DEMONSTRATED = false
```

Economic tension remains: ADD wants weakness in **price** while VALID thesis wants **strong signal (score≥80)** — historically these never coincided (`FULLY_ELIGIBLE_ADD_WINDOWS=0`).

---

## Phase 7 — Historical distribution (Parallel V2 journals)

```text
OPEN_CYCLE_COUNT                 15
ACTIVE_OPEN_CYCLE_REEVALUATIONS  1271
THESIS_VALID_COUNT               1113   (87.6%)
THESIS_WATCH_COUNT                158   (12.4%)
THESIS_INVALID_COUNT                0   (while OPEN; close sets INVALID separately)
ACCUMULATION_ALLOWED_COUNT       1271
ACCUMULATION_STOPPED_EVENTS        12
THRESHOLD_HITS_WHILE_VALID          0
THRESHOLD_HITS_WHILE_WATCH          2
THRESHOLD_HITS_WHILE_STOPPED       18
FULLY_ELIGIBLE_ADD_WINDOWS          0
```

---

## Phase 8 — Sensitivity (read-only)

| Hit | NEAREST_FAILED_CONDITION | DISTANCE_TO_PASS |
|-----|--------------------------|------------------|
| 1 | score ≥ 80 (or BUY PDE) | **+20 score** (60→80) |
| 2 | score ≥ 80 (or BUY PDE) | **+20 score** |

If score had been ≥80 at those marks → thesis VALID → `price_drop_reached` true → policy would emit ADD_TRANCHE (subject to cash/budget/profit gate). No threshold change recommended in this audit.

---

## Phase 9 — Classification

```text
PRIMARY:   THESIS_CORRECTLY_DETERIORATED_AFTER_OPEN
SECONDARY: WATCH_CORRECTLY_BLOCKS_ACCUMULATION
ALSO:      INSUFFICIENT_HISTORICAL_EVENTS (0 fully eligible ADD windows)
NOT:       OPEN_AND_ADD_USE_INCONSISTENT_THRESHOLDS
NOT:       PRICE_DROP_CAUSES_SELF_BLOCKING_WATCH (as mechanical loop)
```

```text
ECONOMIC_POLICY_COHERENT = true (same thesis bar)
CORE_V2_ACCUMULATION_FEASIBLE = unproven in this sample (0 windows)
CODE_CHANGE_RECOMMENDED = false
RECOMMENDED_NEXT_STEP = CONTINUE_OBSERVATION — wait for OPEN∧VALID∧drop≥3% coincidence; do not relax filters in this sprint
```
