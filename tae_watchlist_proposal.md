# TAE Watchlist Proposal

**Generated:** 2026-06-30T13:12:25.915233+00:00
**Mode:** PAPER_ONLY_ADVISORY
**Safety:** PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE | NO_WATCHLIST_WRITE

## Summary

- Current watchlist count: **25**
- Open positions: **4**
- Candidates consumed: **63**
- New candidates: **38**
- Recommended additions (max 10): **0**
- Global data sufficient: **True**

## Sources

- `global_candidates.csv`: present=True status=OK rows=15 age_h=0.03
- `global_market_scanner.csv`: present=True status=OK rows=10 age_h=0.03
- `global_opportunity_ranking.csv`: present=True status=OK rows=15 age_h=0.03
- `multi_market_candidates.csv`: present=True status=OK rows=15 age_h=0.85
- `regional_strength.csv`: present=True status=OK rows=4 age_h=0.03
- `sector_rotation.csv`: present=True status=OK rows=11 age_h=0.03
- `tae_candidate_strategy_registry.json`: present=True status=OK rows=3 age_h=0.0
- `tae_continuous_strategy_ranking.json`: present=True status=OK rows=3 age_h=0.0
- `watchlist_candidates.csv`: present=True status=OK rows=53 age_h=0.86

## Recommended Additions (max 10)

- *(none)*

## Top 10 (all sources)

- QQQ (US) rank=99.2 [already_held] source=global_opportunity_ranking.csv
- SPY (US) rank=99.2 [already_held] source=global_opportunity_ranking.csv
- PG (US) rank=98.3 [already_in_watchlist] source=watchlist_candidates.csv
- PM (US) rank=98.3 [already_in_watchlist] source=watchlist_candidates.csv
- DIA (US) rank=92.32 [already_in_watchlist] source=watchlist_candidates.csv
- PANW (US) rank=91.93 [market_closed] source=watchlist_candidates.csv
- MU (US) rank=91.42 [already_in_watchlist] source=watchlist_candidates.csv
- V (US) rank=91.33 [market_closed] source=watchlist_candidates.csv
- MC.PA (EU) rank=89.9 [already_held] source=global_opportunity_ranking.csv
- MA (US) rank=88.04 [market_closed] source=watchlist_candidates.csv

## Risk Notes

- ETF regional scanner leaders (global_market_scanner.csv, OK): US_LARGE_CAP(0.0), US_TECH(0.0), US_BLUE_CHIP(0.0)
- Regional strength (regional_strength.csv, OK): US=0.0, EUROPE=0.0, UK=0.0, ASIA=0.0
- Sector rotation leaders (sector_rotation.csv, OK): TECHNOLOGY(0.0), FINANCIALS(0.0), HEALTHCARE(0.0)
- Proposal sourced from tae_candidate_queue.json (recommended_action=WAIT_FOR_MARKET_OPEN).
- Candidate queue recommends WAIT_FOR_MARKET_OPEN — promotion candidates may exist but sessions are closed.
- This proposal does NOT modify watchlist.txt — operator review required.

## Strategy Context (non-ticker)

- Registry verdict: CANDIDATE_STRATEGY_REGISTRY_READY
- Strategy `SCORE_90_PLUS_NO_CLOSED_FREEZE` score=0.9315 decision=STRONG_PAPER_CANDIDATE
- Strategy `LIVE_BASELINE` score=0.2934 decision=BASELINE_REFERENCE
- Strategy `SCORE_100_CURRENT_ONLY` score=0.2529 decision=INSUFFICIENT_SAMPLE

## Governance

- Does **NOT** write `watchlist.txt`
- Does **NOT** execute trades
- Operator must manually review before any watchlist change
