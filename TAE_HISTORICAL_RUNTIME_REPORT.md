# TAE Historical Runtime Report

**Generated:** 2026-09-12T15:00:42+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_CHANGE
**All fresh:** **True**
**Confidence penalty:** 0.00

## Source audit (after refresh)

| source | path | age (h) | max (h) | status | refresh |
| --- | --- | --- | --- | --- | --- |
| historical_intelligence_csv | `historical_intelligence.csv` | 126.01 | 24.0 | **STALE_REFRESH_OWNER_ABSENT** | no |
| multi_horizon_backtest_csv | `multi_horizon_backtest.csv` | 3.99 | 24.0 | **FRESH** | no |
| global_market_scanner_csv | `global_market_scanner.csv` | 3.98 | 24.0 | **FRESH** | no |
| regional_strength_csv | `regional_strength.csv` | 3.98 | 24.0 | **FRESH** | no |
| strategic_horizon_summary | `strategic_horizon_summary.txt` | 3.98 | 24.0 | **FRESH** | no |
| horizon_validation_summary | `horizon_validation_summary.txt` | 3.98 | 24.0 | **FRESH** | no |
| strategic_intelligence_summary | `strategic_intelligence_summary.txt` | 3.98 | 24.0 | **FRESH** | no |
| horizon_vote_summary | `horizon_vote_summary.txt` | 3.98 | 24.0 | **FRESH** | no |

## Stale sources (critical)

- None — all critical historical/strategic sources fresh

## Dependent recompute

- growth_intelligence: skipped (artifact still fresh)
- strategic_allocation_runtime: skipped (recompute owner intentionally absent on HEAD)

## Consumers

- Multi-Horizon / Paper Decisions / Learning-to-Profit / Paper Experiments / DPE context

## Safety

| Rule | Status |
| --- | --- |
| NO_BROKER | ✅ |
| NO_LIVE_CHANGE | ✅ |
| No new engines | ✅ |
| Never silent stale | ✅ |
