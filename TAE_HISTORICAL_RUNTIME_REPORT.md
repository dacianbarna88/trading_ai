# TAE Historical Runtime Report

**Generated:** 2026-07-07T14:47:13+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_CHANGE
**All fresh:** **True**
**Confidence penalty:** 0.00

## Source audit (after refresh)

| source | path | age (h) | max (h) | status | refresh |
| --- | --- | --- | --- | --- | --- |
| historical_intelligence_csv | `historical_intelligence.csv` | 0.02 | 24.0 | **FRESH** | no |
| multi_horizon_backtest_csv | `multi_horizon_backtest.csv` | 0.02 | 24.0 | **FRESH** | no |
| global_market_scanner_csv | `global_market_scanner.csv` | 0.02 | 24.0 | **FRESH** | no |
| regional_strength_csv | `regional_strength.csv` | 0.01 | 24.0 | **FRESH** | no |
| strategic_horizon_summary | `strategic_horizon_summary.txt` | None | 24.0 | **MISSING** | yes |
| horizon_validation_summary | `horizon_validation_summary.txt` | 0.01 | 24.0 | **FRESH** | no |
| strategic_intelligence_summary | `strategic_intelligence_summary.txt` | 0.01 | 24.0 | **FRESH** | no |
| horizon_vote_summary | `horizon_vote_summary.txt` | 0.01 | 24.0 | **FRESH** | no |

## Stale sources (critical)

- None — all critical historical/strategic sources fresh

## Dependent recompute

- growth_intelligence: skipped (artifact still fresh)
- strategic_allocation_runtime: skipped (artifact still fresh)

## Consumers

- Multi-Horizon / Paper Decisions / Learning-to-Profit / Paper Experiments / DPE context

## Safety

| Rule | Status |
| --- | --- |
| NO_BROKER | ✅ |
| NO_LIVE_CHANGE | ✅ |
| No new engines | ✅ |
| Never silent stale | ✅ |
