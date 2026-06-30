# TAE Watchlist Proposal

**Generated:** 2026-06-30T13:32:07.458264+00:00
**Mode:** PAPER_ONLY_ADVISORY
**Safety:** PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE | NO_WATCHLIST_WRITE

## Summary

- Current watchlist count: **25**
- Open positions: **8**
- Candidates consumed: **63**
- New candidates: **38**
- Recommended additions (max 10): **10**
- Global data sufficient: **True**

## Sources

- `global_candidates.csv`: present=True status=OK rows=15 age_h=0.03
- `global_market_scanner.csv`: present=True status=OK rows=10 age_h=0.04
- `global_opportunity_ranking.csv`: present=True status=OK rows=15 age_h=0.03
- `multi_market_candidates.csv`: present=True status=OK rows=15 age_h=1.18
- `regional_strength.csv`: present=True status=OK rows=4 age_h=0.04
- `sector_rotation.csv`: present=True status=OK rows=11 age_h=0.04
- `tae_candidate_strategy_registry.json`: present=True status=OK rows=3 age_h=0.01
- `tae_continuous_strategy_ranking.json`: present=True status=OK rows=3 age_h=0.01
- `watchlist_candidates.csv`: present=True status=OK rows=53 age_h=1.18

## Recommended Additions (max 10)

- **PANW** (US) rank=93.29 source=`watchlist_candidates.csv` signal=WAIT
- **V** (US) rank=92.69 source=`watchlist_candidates.csv` signal=WAIT
- **MA** (US) rank=89.4 source=`watchlist_candidates.csv` signal=WAIT
- **UNH** (US) rank=88.51 source=`watchlist_candidates.csv` signal=WAIT
- **AMD** (US) rank=88.21 source=`watchlist_candidates.csv` signal=WAIT
- **CAT** (US) rank=88.21 source=`watchlist_candidates.csv` signal=WAIT
- **SNOW** (US) rank=87.01 source=`watchlist_candidates.csv` signal=WAIT
- **BRK-B** (US) rank=85.82 source=`watchlist_candidates.csv` signal=WAIT
- **IBM** (US) rank=85.82 source=`watchlist_candidates.csv` signal=WAIT
- **INTC** (US) rank=85.82 source=`watchlist_candidates.csv` signal=WAIT

## Top 10 (all sources)

- PM (US) rank=100.0 [already_held] source=watchlist_candidates.csv
- QQQ (US) rank=100.0 [already_held] source=global_opportunity_ranking.csv
- SPY (US) rank=100.0 [already_held] source=global_opportunity_ranking.csv
- PG (US) rank=93.83 [already_held] source=watchlist_candidates.csv
- MC.PA (EU) rank=93.33 [already_held] source=global_opportunity_ranking.csv
- PANW (US) rank=93.29 [promotion_eligible] source=watchlist_candidates.csv
- DIA (US) rank=93.23 [already_held] source=watchlist_candidates.csv
- MU (US) rank=93.23 [already_held] source=watchlist_candidates.csv
- ULVR.L (UK) rank=92.73 [already_held] source=global_opportunity_ranking.csv
- V (US) rank=92.69 [promotion_eligible] source=watchlist_candidates.csv

## Risk Notes

- ETF regional scanner leaders (global_market_scanner.csv, OK): US_LARGE_CAP(0.0), US_TECH(0.0), US_BLUE_CHIP(0.0)
- Regional strength (regional_strength.csv, OK): US=0.0, EUROPE=0.0, UK=0.0, ASIA=0.0
- Sector rotation leaders (sector_rotation.csv, OK): TECHNOLOGY(0.0), FINANCIALS(0.0), HEALTHCARE(0.0)
- Proposal sourced from tae_candidate_queue.json (recommended_action=PROMOTE_MAX_10).
- This proposal does NOT modify watchlist.txt — operator review required.

## Strategy Context (non-ticker)

- Registry verdict: CANDIDATE_STRATEGY_REGISTRY_READY
- Strategy `SCORE_90_PLUS_NO_CLOSED_FREEZE` score=0.9415 decision=STRONG_PAPER_CANDIDATE
- Strategy `LIVE_BASELINE` score=0.2927 decision=BASELINE_REFERENCE
- Strategy `SCORE_100_CURRENT_ONLY` score=0.2629 decision=INSUFFICIENT_SAMPLE

## Governance

- Does **NOT** write `watchlist.txt`
- Does **NOT** execute trades
- Operator must manually review before any watchlist change
