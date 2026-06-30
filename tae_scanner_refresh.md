# TAE Scanner Refresh

**Generated:** 2026-06-30T11:34:04.650568+00:00
**Verdict:** OK
**Total runtime:** 91.48s

## Steps

| Step | Status | Runtime (s) | Artifact | Rows | Freshness (h) |
|------|--------|-------------|----------|------|---------------|
| global_market_scanner | OK | 18.89 | global_market_scanner.csv | 10 | 0.0001 |
| regional_strength_aggregator | OK | 1.405 | regional_strength.csv | 4 | 0.0 |
| sector_rotation_scanner | OK | 13.285 | sector_rotation.csv | 11 | 0.0001 |
| us_market_scanner | OK | 15.096 | watchlist_candidates.csv | 53 | 0.0001 |
| multi_market_scanner | OK | 5.872 | multi_market_candidates.csv | 15 | 0.0001 |
| global_candidates | OK | 1.739 | global_candidates.csv | 15 | 0.0001 |
| global_opportunity_ranking | OK | 1.427 | global_opportunity_ranking.csv | 15 | 0.0 |
| historical_results_analysis | OK | 3.128 | tae_historical_results_analysis.json | None | 0.0001 |
| strategy_evolution_daily_runner | OK | 2.387 | tae_continuous_strategy_ranking.json | None | 0.0001 |
| live_signals_historical_enrich | OK | 1.997 | tae_live_signals_historical_enrich.json | None | 0.0001 |
| research_runtime | OK | 12.64 | tae_research_runtime.json | None | 0.0001 |
| live_signals_research_enrich | OK | 1.982 | tae_live_signals_research_enrich.json | None | 0.0001 |
| committee_runtime | OK | 6.436 | tae_committee_runtime.json | None | 0.0001 |
| live_signals_committee_enrich | OK | 1.949 | tae_live_signals_committee_enrich.json | None | 0.0001 |
| candidate_queue_builder | OK | 0.156 | tae_candidate_queue.json | None | 0.0 |
| watchlist_proposal | OK | 0.137 | tae_watchlist_proposal.json | None | 0.0 |
| actionable_signal_audit | OK | 2.932 | tae_actionable_signal_audit.json | None | 0.0001 |

## Downstream

- Candidate queue action: **WAIT_FOR_MARKET_OPEN**
- Promotion eligible: **0**
- Watchlist proposal recommended additions: **0**
- Watchlist proposal queue action: **WAIT_FOR_MARKET_OPEN**

## Governance

- Does **NOT** write `watchlist.txt`
- Does **NOT** auto-promote watchlist
- Does **NOT** modify live_bot BUY/SELL logic
