# TAE Validation → Capital Allocation Audit

**Generated:** 2026-07-15  
**Verdict:** `VALIDATION_TO_CAPITAL_ALLOCATION_CLOSED`  
**Mode:** PAPER_ONLY · NO_BROKER · live_promotion_allowed=false

Machine twin: `tae_validation_to_capital_allocation_audit.json`  
Challenger twin: `TAE_EXPERIMENT_CAPITAL_CHALLENGER_REPORT.md` / `tae_experiment_capital_challenger_report.json`

---

## Mission closed

Missing constitutional arrow **Validation → Capital Allocation** is now observable through existing systems:

1. Eligibility classification (not raw PROMISING)
2. `paper_experiment_action` → existing PDE action mapping
3. Action-specific score evidence (no uniform boost)
4. Adaptive weights consume actionable `experiment_results.json`
5. Bounded REDUCE challengers execute via existing paper execution
6. Challenger lifecycle registry: `runtime_outputs/learning_to_profit/capital_challengers.json`

PDE remains single final authority. Hard Risk remains non-bypassable. Capital base **$30,000**.

---

## Phase 1–2 — Eligibility + mappings (8 PROMISING)

| hypothesis_id | mapping | status | authorize | why |
| --- | --- | --- | --- | --- |
| LTB-DPE-PHIL-001 | none | **PORTFOLIO_POLICY_CANDIDATE** | No | Philosophy bias only |
| LTB-OPP-HSBA.L-01 | ROTATE→**REDUCE_PAPER** | **ACTIONABLE_CAPITAL_CANDIDATE** | Yes | Held + CRITICAL → bounded REDUCE |
| LTB-OPP-MU-02 | ROTATE_PAPER | **NOT_EXECUTABLE** | No | Hard Risk CRITICAL block |
| LTB-OPP-AMAT-03 | ROTATE_PAPER | **NOT_EXECUTABLE** | No | Hard Risk CRITICAL block |
| LTB-PROT-AMAT | REDUCE_PAPER | **NOT_EXECUTABLE** | No | No open PAPER position |
| LTB-PROT-AAPL | **REDUCE_PAPER** | **ACTIONABLE_CAPITAL_CANDIDATE** | Yes | Held protect/trim |
| LTB-PROT-PG | **REDUCE_PAPER** | **ACTIONABLE_CAPITAL_CANDIDATE** | Yes | Held protect/trim |
| LTB-PROT-GE | **REDUCE_PAPER** | **ACTIONABLE_CAPITAL_CANDIDATE** | Yes | Held protect/trim |

Exact maps (existing PDE verbs only):

- `PAPER_TRAILING_PROTECT_TRIM` → `REDUCE_PAPER` (capital-moving trim)
- `PAPER_REALLOCATION` → `ROTATE_PAPER` (held); CRITICAL held → bounded `REDUCE_PAPER`
- `PAPER_DPE_PHILOSOPHY_WEIGHT` → portfolio policy bias only (no trade)

---

## Phase 3–4 — Challenger execution (cycle evidence)

Before challenger cycle:

- PAPER total **$29,815.23** · cash **$11,759.59** · realized **$-724.62** · total PnL **$-525.69**

After first full cycle with challengers:

- PAPER total **$29,813.77** · cash **$13,339.83** · realized **$-694.28**
- **4 EXECUTED REDUCE trades** (`is_trade=true`)

| ticker | experiment | fill shares | realized PnL | cash lift |
| --- | --- | --- | --- | --- |
| HSBA.L | LTB-OPP-HSBA.L-01 | 0.278203 | **+$3.95** | yes |
| PG | LTB-PROT-PG | 3.36814 | **+$2.49** | yes |
| AAPL | LTB-PROT-AAPL | 1.62006 | **+$23.95** | yes |
| GE | LTB-PROT-GE | 0.386443 | **$-0.05** | yes |

Capital allocation changed: **yes** (cash +$1,580.24 from trims; shares reduced).  
AMAT/MU: **no capital** (Hard Risk / no position).

Decision fields now include: `experiment_id`, `experiment_verdict`, `capital_candidate_status`, `experiment_action_mapping`, `experiment_score_delta`, `proposed_allocation_usd`, `allocation_authorized`, `allocation_block_reason`, `evidence_quality`.

---

## Phase 5 — Adaptive weights

`EXPERIMENTS_JSON` is consumed (actionable rows only).  
`REDUCE_PAPER` weight rose with experiment PROMISING/CONTINUE attribution (capped daily Δ ±0.02).  
BUY weight not loosened by philosophy PROMISING.

---

## Phase 6 — Replay summary

4 eligible / 4 ineligible among the 8 PROMISING targets.  
Hard Risk blocks on AMAT/MU preserved.  
No invented BUY from reallocations without held source.

---

## Phase 7 — Validation

Two consecutive `full-paper-cycle` runs completed without hang.

| Check | Result |
| --- | --- |
| Eligible experiment changed executable decision | **Yes** — REDUCE_PAPER for AAPL/PG/GE/HSBA.L |
| Raw PROMISING bypass PDE | **No** |
| Duplicate orders/trades | None observed on challenger path |
| Profit Integrity | **PASS** (`PAPER_PROFIT_INTEGRITY_CLOSED`) |
| Reconciliation | **PASS** |
| Capital base | **$30,000 CONFIRMED** |
| Hard Risk sync AMAT/MU | SKIP / NOT_EXECUTABLE |
| Constitutional evolution | `loop_closed=true` |

---

## Phase 8 — Tests

`tae_validation_to_capital_allocation_test` + existing PDE/execution/state/pipeline suites — **85 tests OK**.

---

## Files changed

- `tae_paper_decision_engine.py` — eligibility, mapping, action-specific evidence, challenger elevation/switch, registry
- `tae_adaptive_paper_weights.py` — wire actionable experiment_results
- `tae_paper_execution.py` — attribute experiment_id into rule_sources
- `tae_structural_governance.py` — observe challenger registry post-exec
- `tae_validation_to_capital_allocation_test.py` — new tests

---

## Final verdict

**`VALIDATION_TO_CAPITAL_ALLOCATION_CLOSED`**
