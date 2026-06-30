# TAE Watchlist Proposal

**Generated:** 2026-06-30T10:08:08.008037+00:00
**Mode:** PAPER_ONLY_ADVISORY
**Safety:** PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE | NO_WATCHLIST_WRITE

## Summary

- Current watchlist count: **15**
- Open positions: **4**
- Candidates consumed: **63**
- New candidates: **30**
- Recommended additions (max 10): **10**
- Global data sufficient: **True**

## Sources

- `global_candidates.csv`: present=True status=OK rows=15 age_h=0.0
- `global_market_scanner.csv`: present=True status=OK rows=10 age_h=0.02
- `global_opportunity_ranking.csv`: present=True status=OK rows=15 age_h=0.0
- `multi_market_candidates.csv`: present=True status=OK rows=15 age_h=0.0
- `regional_strength.csv`: present=True status=OK rows=4 age_h=0.01
- `sector_rotation.csv`: present=True status=OK rows=11 age_h=0.01
- `tae_candidate_strategy_registry.json`: present=True status=OK rows=3 age_h=39.18
- `tae_continuous_strategy_ranking.json`: present=True status=OK rows=3 age_h=39.18
- `watchlist_candidates.csv`: present=True status=OK rows=53 age_h=0.01
- `watchlist_global.txt`: present=True status=OK rows=15 age_h=0.0

## Recommended Additions (max 10)

- **DIA** (US) rank=105.0 source=`watchlist_candidates.csv` signal=STRONG BUY
- **LLY** (US) rank=100.0 source=`watchlist_candidates.csv` signal=STRONG BUY
- **ABBV** (US) rank=85.0 source=`watchlist_candidates.csv` signal=WAIT
- **AMAT** (US) rank=85.0 source=`watchlist_candidates.csv` signal=WAIT
- **MRK** (US) rank=85.0 source=`watchlist_candidates.csv` signal=WAIT
- **MU** (US) rank=85.0 source=`watchlist_candidates.csv` signal=WAIT
- **PG** (US) rank=85.0 source=`watchlist_candidates.csv` signal=WAIT
- **PM** (US) rank=85.0 source=`watchlist_candidates.csv` signal=WAIT
- **GE** (US) rank=80.0 source=`watchlist_candidates.csv` signal=WAIT
- **HD** (US) rank=80.0 source=`watchlist_candidates.csv` signal=WAIT

## Top 10 (all sources)

- DIA (US) rank=105.0 [new_candidate] source=watchlist_candidates.csv
- LLY (US) rank=100.0 [new_candidate] source=watchlist_candidates.csv
- ABBV (US) rank=85.0 [new_candidate] source=watchlist_candidates.csv
- AMAT (US) rank=85.0 [new_candidate] source=watchlist_candidates.csv
- MRK (US) rank=85.0 [new_candidate] source=watchlist_candidates.csv
- MU (US) rank=85.0 [new_candidate] source=watchlist_candidates.csv
- PG (US) rank=85.0 [new_candidate] source=watchlist_candidates.csv
- PM (US) rank=85.0 [new_candidate] source=watchlist_candidates.csv
- GE (US) rank=80.0 [new_candidate] source=watchlist_candidates.csv
- HD (US) rank=80.0 [new_candidate] source=watchlist_candidates.csv

## Risk Notes

- ETF regional scanner leaders (global_market_scanner.csv, OK): US_SMALL_CAP(17.21), US_TECH(14.61), JAPAN(10.94)
- Regional strength (regional_strength.csv, OK): US=12.37, EUROPE=7.6, UK=4.89, ASIA=2.84
- Sector rotation leaders (sector_rotation.csv, OK): TECHNOLOGY(21.89), INDUSTRIALS(13.64), HEALTHCARE(10.32)
- This proposal does NOT modify watchlist.txt — operator review required.

## Strategy Context (non-ticker)

- Registry verdict: CANDIDATE_STRATEGY_REGISTRY_READY
- Strategy `SCORE_90_PLUS_NO_CLOSED_FREEZE` score=0.9336 decision=STRONG_PAPER_CANDIDATE
- Strategy `SCORE_100_CURRENT_ONLY` score=0.2238 decision=INSUFFICIENT_SAMPLE
- Strategy `LIVE_BASELINE` score=0.2135 decision=BASELINE_REFERENCE

## Governance

- Does **NOT** write `watchlist.txt`
- Does **NOT** execute trades
- Operator must manually review before any watchlist change
