# TAE Scanner Refresh

**Generated:** 2026-06-30T12:30:25.564957+00:00
**Verdict:** OK
**Total runtime:** 91.655s

## Steps

| Step | Status | Runtime (s) | Artifact | Rows | Freshness (h) |
|------|--------|-------------|----------|------|---------------|
| global_market_scanner | OK | 2.498 | global_market_scanner.csv | 10 | 0.0001 |
| regional_strength_aggregator | OK | 1.32 | regional_strength.csv | 4 | 0.0001 |
| sector_rotation_scanner | OK | 2.671 | sector_rotation.csv | 11 | 0.0001 |
| us_market_scanner | OK | 3.165 | watchlist_candidates.csv | 53 | 0.1334 |
| multi_market_scanner | OK | 2.079 | multi_market_candidates.csv | 15 | 0.1324 |
| global_candidates | OK | 1.283 | global_candidates.csv | 15 | 0.0001 |
| global_opportunity_ranking | OK | 1.289 | global_opportunity_ranking.csv | 15 | 0.0 |
| historical_results_analysis | OK | 2.203 | tae_historical_results_analysis.json | None | 0.0001 |
| strategy_evolution_daily_runner | OK | 2.067 | tae_continuous_strategy_ranking.json | None | 0.0001 |
| live_signals_historical_enrich | OK | 2.005 | tae_live_signals_historical_enrich.json | None | 0.0001 |
| research_runtime | OK | 6.748 | tae_research_runtime.json | None | 0.0001 |
| live_signals_research_enrich | OK | 1.956 | tae_live_signals_research_enrich.json | None | 0.0001 |
| committee_runtime | OK | 6.452 | tae_committee_runtime.json | None | 0.0001 |
| live_signals_committee_enrich | OK | 1.984 | tae_live_signals_committee_enrich.json | None | 0.0001 |
| learning_runtime | OK | 5.921 | tae_learning_runtime.json | None | 0.0001 |
| strategic_allocation_runtime | OK | 5.142 | tae_strategic_allocation_runtime.json | None | 0.0001 |
| live_signals_allocation_enrich | OK | 2.017 | tae_live_signals_allocation_enrich.json | None | 0.0001 |
| meta_intelligence_runtime | OK | 6.493 | tae_meta_intelligence_runtime.json | None | 0.0001 |
| live_signals_meta_enrich | OK | 2.015 | tae_live_signals_meta_enrich.json | None | 0.0001 |
| strategy_discovery_runtime | OK | 4.14 | tae_strategy_discovery_runtime.json | None | 0.0001 |
| strategy_simulation_runtime | OK | 11.11 | tae_strategy_simulation_runtime.json | None | 0.0001 |
| event_memory_runtime | OK | 3.917 | tae_event_memory_runtime.json | None | 0.0001 |
| counterfactual_runtime | OK | 8.426 | tae_counterfactual_runtime.json | None | 0.0001 |
| unified_runtime | OK | 2.013 | tae_unified_runtime.json | None | 0.0001 |
| candidate_queue_builder | OK | 0.156 | tae_candidate_queue.json | None | 0.0 |
| watchlist_proposal | OK | 0.139 | tae_watchlist_proposal.json | None | 0.0 |
| actionable_signal_audit | OK | 2.389 | tae_actionable_signal_audit.json | None | 0.0001 |

## Downstream

- Candidate queue action: **WAIT_FOR_MARKET_OPEN**
- Promotion eligible: **0**
- Watchlist proposal recommended additions: **0**
- Watchlist proposal queue action: **WAIT_FOR_MARKET_OPEN**

## Governance

- Does **NOT** write `watchlist.txt`
- Does **NOT** auto-promote watchlist
- Does **NOT** modify live_bot BUY/SELL logic
