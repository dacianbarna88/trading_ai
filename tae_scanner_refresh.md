# TAE Scanner Refresh

**Generated:** 2026-06-30T10:49:21.131706+00:00
**Verdict:** OK
**Total runtime:** 53.341s

## Steps

| Step | Status | Runtime (s) | Artifact | Rows | Freshness (h) |
|------|--------|-------------|----------|------|---------------|
| global_market_scanner | OK | 12.478 | global_market_scanner.csv | 10 | 0.0001 |
| regional_strength_aggregator | OK | 1.241 | regional_strength.csv | 4 | 0.0 |
| sector_rotation_scanner | OK | 12.42 | sector_rotation.csv | 11 | 0.0001 |
| us_market_scanner | OK | 14.883 | watchlist_candidates.csv | 53 | 0.0001 |
| multi_market_scanner | OK | 5.959 | multi_market_candidates.csv | 15 | 0.0001 |
| global_candidates | OK | 1.275 | global_candidates.csv | 15 | 0.0 |
| global_opportunity_ranking | OK | 1.269 | global_opportunity_ranking.csv | 15 | 0.0 |
| candidate_queue_builder | OK | 0.149 | tae_candidate_queue.json | None | 0.0 |
| watchlist_proposal | OK | 0.145 | tae_watchlist_proposal.json | None | 0.0 |
| actionable_signal_audit | OK | 3.51 | tae_actionable_signal_audit.json | None | 0.0001 |

## Downstream

- Candidate queue action: **WAIT_FOR_MARKET_OPEN**
- Promotion eligible: **0**
- Watchlist proposal recommended additions: **0**
- Watchlist proposal queue action: **WAIT_FOR_MARKET_OPEN**

## Governance

- Does **NOT** write `watchlist.txt`
- Does **NOT** auto-promote watchlist
- Does **NOT** modify live_bot BUY/SELL logic
