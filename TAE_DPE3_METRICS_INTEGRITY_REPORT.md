# TAE DPE-3.1 — Metrics Integrity Audit Report

**Date:** 2026-09-03T13:15:11+00:00
**Sprint:** DPE-3.1 Metrics Integrity Audit & Synchronization
**Metrics schema:** dpe.paper_metrics.v2
**Status:** PASS

## Consistency matrix

| Layer | Field | Value |
| --- | --- | --- |
| execution_jobs.jsonl | jobs_read | 1386 |
| portfolio.json | processed_job_ids | 1386 |
| orders.jsonl | orders_written | 1295 |
| trades.jsonl | trades_written | 1295 |
| metrics.json | historical_actions.total | 1295 |
| metrics.json | new_actions.total | 0 |
| portfolio.json | total_value | 54240.9127 |
| portfolio.json | realized_pnl | -111.6023 |
| portfolio.json | unrealized_pnl | 1524.8985 |
| portfolio.json | cash | 8162.7427 |
| portfolio.json | position_count | 21 |

## Detected mismatches (before fix)

- `jobs_processed=0` while orders/trades contained 33 historical actions
- `hold_count/trim_count` reset to 0 on idempotent re-runs
- `total_trades` tracked current run only, not journal totals
- Reports summarized current run without historical separation

## Corrections applied

- Introduced `dpe.paper_metrics.v2` with `historical_jobs`, `new_jobs`, `historical_actions`, `new_actions`
- Reconcile orders/trades.jsonl on every run for historical totals
- Separate current-run counters (`new_jobs.processed`, `new_actions.*`)
- Added integrity verification checks across all layers
- Updated `executor_report.md` with Historical state / Current execution sections
- Synced `portfolio.json.executor_totals` with journal counts

## Remaining issues

- None — all integrity checks pass after synchronization

## Integrity checks

| check | pass |
| --- | --- |
| orders_equals_trades | ✅ |
| historical_actions_total | ✅ |
| orders_unique_job_ids | ✅ |
| processed_ids_covers_orders | ✅ |
| processed_ids_balance | ✅ |
| new_actions_total | ✅ |
| portfolio_total_value | ✅ |
| portfolio_realized_pnl | ✅ |
| historical_hold_count | ✅ |

## Final verdict

**PASS**

Historical totals and current execution totals are now separated. Idempotency preserved.

## Next sprint

**TAE DPE-4 — Collaborative Paper Executor** (only after PASS)
