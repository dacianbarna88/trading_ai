# TAE Blocker ROI Report

**Generated:** 2026-07-21T23:10:51
**Dominant blocker:** `same_action`
**Verdict:** `BLOCKER_REJECTED`

## Phase 2 — Blocker rankings

| Rank | Blocker | Triggered | Orders prevented | Profits missed | Losses avoided | EV | Net |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | same_action | 11 | 8 | $0.00 | $23.65 | $-23.65 | -8.4730 |
| 2 | policy_skip | 11 | 0 | $0.00 | $0.00 | $0.00 | 0.0000 |
| 3 | hold_not_actionable | 2 | 0 | $0.00 | $2.00 | $-2.00 | -0.0400 |
| 4 | no_change | 1 | 0 | $4.86 | $0.00 | $4.86 | 0.0972 |

## Phase 4 — Baseline vs challenger

| Metric | Baseline | Challenger | Delta |
| --- | ---: | ---: | ---: |
| Opportunity→Order | 4.0% | 4.0% | +0.0% |
| Actionable→Order | 11.1% | 11.1% | +0.0% |
| Orders (cycle) | 1 | 1 | +0 |
| Profit vs base | $-245.92 | $-245.92 | $+0.00 |
| Drawdown | 1.93% | 1.93% | — |
| Profit factor | 0.04 | 0.04 | — |
| Win rate | 22.2% | 22.2% | — |

### Challenger spec

- ID: `same_action_retry_after_non_terminal`
- Parameter: NON_TERMINAL_RETRY_STATUSES
- Change: retry when last order status in ['BLOCKED_FAKE_PROFIT_RISK', 'SKIPPED_NO_MARK_PRICE', 'SKIPPED_NO_POSITION', 'SKIPPED_SWITCH_NOT_AUTHORIZED']

## Post-validation (2 consecutive PAPER cycles, challenger applied then reverted)

- With patch: Orders **1** (HD `retry_after_non_execution:SKIPPED_NO_MARK_PRICE`), Executions **0**
- Profit vs base: **$-185.30 → $-185.30** (unchanged — HD mark still unavailable)
- Integrity: **PASS** | Reconciliation: **PASS** | Hard risk: **no regression**
- Production patch **reverted** — `higher_profit` criterion not met

## Phase 5 — Promotion decision

**BLOCKER_REJECTED** — Promotion criteria failed: higher_profit, conversion_improved. Challenger improves conversion plumbing but lacks closed-trade profit uplift in replay.
