# TAE Watchlist Proposal

**Generated:** 2026-06-30T12:30:23.139046+00:00
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

- `global_candidates.csv`: present=True status=OK rows=15 age_h=0.02
- `global_market_scanner.csv`: present=True status=OK rows=10 age_h=0.02
- `global_opportunity_ranking.csv`: present=True status=OK rows=15 age_h=0.02
- `multi_market_candidates.csv`: present=True status=OK rows=15 age_h=0.15
- `regional_strength.csv`: present=True status=OK rows=4 age_h=0.02
- `sector_rotation.csv`: present=True status=OK rows=11 age_h=0.02
- `tae_candidate_strategy_registry.json`: present=True status=OK rows=3 age_h=0.02
- `tae_continuous_strategy_ranking.json`: present=True status=OK rows=3 age_h=0.02
- `watchlist_candidates.csv`: present=True status=OK rows=53 age_h=0.16

## Recommended Additions (max 10)

- *(none)*

## Top 10 (all sources)

- QQQ (US) rank=96.05 [already_held] source=global_opportunity_ranking.csv
- SPY (US) rank=96.05 [already_held] source=global_opportunity_ranking.csv
- PG (US) rank=95.15 [already_in_watchlist] source=watchlist_candidates.csv
- PM (US) rank=95.15 [already_in_watchlist] source=watchlist_candidates.csv
- MC.PA (EU) rank=87.08 [already_held] source=global_opportunity_ranking.csv
- PANW (US) rank=87.08 [market_closed] source=watchlist_candidates.csv
- DIA (US) rank=86.48 [already_in_watchlist] source=watchlist_candidates.csv
- ULVR.L (UK) rank=86.48 [already_held] source=global_opportunity_ranking.csv
- V (US) rank=86.48 [market_closed] source=watchlist_candidates.csv
- MU (US) rank=85.58 [already_in_watchlist] source=watchlist_candidates.csv

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
- Strategy `LIVE_BASELINE` score=0.2688 decision=BASELINE_REFERENCE
- Strategy `SCORE_100_CURRENT_ONLY` score=0.2529 decision=INSUFFICIENT_SAMPLE

## Governance

- Does **NOT** write `watchlist.txt`
- Does **NOT** execute trades
- Operator must manually review before any watchlist change
