# TAE Watchlist Proposal

**Generated:** 2026-06-30T11:27:10.203754+00:00
**Mode:** PAPER_ONLY_ADVISORY
**Safety:** PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE | NO_WATCHLIST_WRITE

## Summary

- Current watchlist count: **25**
- Open positions: **4**
- Candidates consumed: **63**
- New candidates: **25**
- Recommended additions (max 10): **0**
- Global data sufficient: **True**

## Sources

- `global_candidates.csv`: present=True status=OK rows=15 age_h=0.01
- `global_market_scanner.csv`: present=True status=OK rows=10 age_h=0.02
- `global_opportunity_ranking.csv`: present=True status=OK rows=15 age_h=0.01
- `multi_market_candidates.csv`: present=True status=OK rows=15 age_h=0.01
- `regional_strength.csv`: present=True status=OK rows=4 age_h=0.02
- `sector_rotation.csv`: present=True status=OK rows=11 age_h=0.01
- `tae_candidate_strategy_registry.json`: present=True status=OK rows=3 age_h=0.0
- `tae_continuous_strategy_ranking.json`: present=True status=OK rows=3 age_h=0.0
- `watchlist_candidates.csv`: present=True status=OK rows=53 age_h=0.01

## Recommended Additions (max 10)

- *(none)*

## Top 10 (all sources)

- DIA (US) rank=105.0 [already_in_watchlist] source=watchlist_candidates.csv
- LLY (US) rank=100.0 [already_in_watchlist] source=watchlist_candidates.csv
- ABBV (US) rank=85.0 [already_in_watchlist] source=watchlist_candidates.csv
- AMAT (US) rank=85.0 [already_in_watchlist] source=watchlist_candidates.csv
- MRK (US) rank=85.0 [already_in_watchlist] source=watchlist_candidates.csv
- MU (US) rank=85.0 [already_in_watchlist] source=watchlist_candidates.csv
- PG (US) rank=85.0 [already_in_watchlist] source=watchlist_candidates.csv
- PM (US) rank=85.0 [already_in_watchlist] source=watchlist_candidates.csv
- GE (US) rank=80.0 [already_in_watchlist] source=watchlist_candidates.csv
- HD (US) rank=80.0 [already_in_watchlist] source=watchlist_candidates.csv

## Risk Notes

- ETF regional scanner leaders (global_market_scanner.csv, OK): US_SMALL_CAP(17.21), US_TECH(14.61), JAPAN(10.94)
- Regional strength (regional_strength.csv, OK): US=12.37, EUROPE=7.6, UK=4.89, ASIA=2.84
- Sector rotation leaders (sector_rotation.csv, OK): TECHNOLOGY(21.89), INDUSTRIALS(13.64), HEALTHCARE(10.32)
- Proposal sourced from tae_candidate_queue.json (recommended_action=WAIT_FOR_MARKET_OPEN).
- Candidate queue recommends WAIT_FOR_MARKET_OPEN — promotion candidates may exist but sessions are closed.
- This proposal does NOT modify watchlist.txt — operator review required.

## Strategy Context (non-ticker)

- Registry verdict: CANDIDATE_STRATEGY_REGISTRY_READY
- Strategy `SCORE_90_PLUS_NO_CLOSED_FREEZE` score=0.9315 decision=STRONG_PAPER_CANDIDATE
- Strategy `LIVE_BASELINE` score=0.2717 decision=BASELINE_REFERENCE
- Strategy `SCORE_100_CURRENT_ONLY` score=0.2529 decision=INSUFFICIENT_SAMPLE

## Governance

- Does **NOT** write `watchlist.txt`
- Does **NOT** execute trades
- Operator must manually review before any watchlist change
