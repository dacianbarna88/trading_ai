# TAE Experiment Capital Challenger Report

**Generated:** 2026-07-15  
**Mode:** PAPER_ONLY · NO_BROKER · live_promotion_allowed=false  
**Lifecycle:** `PROMISING → CAPITAL_CHALLENGER → EXECUTED_PAPER → OBSERVED → PROMOTED/REVERTED`

Artifact: `runtime_outputs/learning_to_profit/capital_challengers.json`  
JSON twin: `tae_experiment_capital_challenger_report.json`

---

## Rules

- PROMISING alone never authorizes capital
- Only mapped existing PDE actions execute (`REDUCE_PAPER` primary challenger path)
- Max trim notional bounded (`CHALLENGER_MAX_ALLOCATION_USD=400`, trim fraction 10%)
- Hard Risk cannot be bypassed (AMAT/MU remain blocked)
- Decision State switch authorized only via explicit `capital_challenger:<experiment_id>`
- Rollback condition: negative realized outcome → REVERT/RETIRE hint

---

## Executed challenger fills (validation cycle)

| experiment_id | ticker | action | fill | realized PnL | promotion hint |
| --- | --- | --- | --- | --- | --- |
| LTB-OPP-HSBA.L-01 | HSBA.L | REDUCE_PAPER | 0.278203 | +3.9505 | PROMOTED_CANDIDATE |
| LTB-PROT-PG | PG | REDUCE_PAPER | 3.36814 | +2.4924 | PROMOTED_CANDIDATE |
| LTB-PROT-AAPL | AAPL | REDUCE_PAPER | 1.62006 | +23.9526 | PROMOTED_CANDIDATE |
| LTB-PROT-GE | GE | REDUCE_PAPER | 0.386443 | −0.0464 | REVERT_OR_RETIRE |

Ineligible (report-only / blocked):

| experiment_id | status |
| --- | --- |
| LTB-DPE-PHIL-001 | PORTFOLIO_POLICY_CANDIDATE |
| LTB-OPP-MU-02 | NOT_EXECUTABLE (Hard Risk) |
| LTB-OPP-AMAT-03 | NOT_EXECUTABLE (Hard Risk) |
| LTB-PROT-AMAT | NOT_EXECUTABLE (no position) |

---

## Portfolio impact (challenger cycle)

| metric | before | after |
| --- | --- | --- |
| cash | $11,759.59 | $13,339.83 |
| realized PnL | $-724.62 | $-694.28 |
| total value | $29,815.23 | $29,813.77 |

Integrity PASS · Reconciliation PASS · Capital base $30,000 · PDE final authority preserved.
