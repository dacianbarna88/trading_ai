# TAE Global Candidate Queue

**Generated:** 2026-06-30T13:32:07.053557+00:00
**Mode:** CONTROLLED_INTEGRATION
**Safety:** CONTROLLED_INTEGRATION | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE | NO_WATCHLIST_WRITE | NO_BUY_SELL_LOGIC

## Summary

- Total candidates processed: **63**
- Promotion eligible: **38**
- Already held: **8**
- Already in watchlist: **17**
- Market closed: **0**
- Recommended action: **PROMOTE_MAX_10**

## Promotion Queue

**Action:** PROMOTE_MAX_10

### Top 10 promotion eligible

- **PANW** (US) rank=93.29 source=`watchlist_candidates.csv` open=True
- **V** (US) rank=92.69 source=`watchlist_candidates.csv` open=True
- **MA** (US) rank=89.4 source=`watchlist_candidates.csv` open=True
- **UNH** (US) rank=88.51 source=`watchlist_candidates.csv` open=True
- **AMD** (US) rank=88.21 source=`watchlist_candidates.csv` open=True
- **CAT** (US) rank=88.21 source=`watchlist_candidates.csv` open=True
- **SNOW** (US) rank=87.01 source=`watchlist_candidates.csv` open=True
- **BRK-B** (US) rank=85.82 source=`watchlist_candidates.csv` open=True
- **IBM** (US) rank=85.82 source=`watchlist_candidates.csv` open=True
- **INTC** (US) rank=85.82 source=`watchlist_candidates.csv` open=True

### Top 25 monitor

- PANW (US) [PROMOTION_ELIGIBLE] rank=93.29
- V (US) [PROMOTION_ELIGIBLE] rank=92.69
- MA (US) [PROMOTION_ELIGIBLE] rank=89.4
- UNH (US) [PROMOTION_ELIGIBLE] rank=88.51
- AMD (US) [PROMOTION_ELIGIBLE] rank=88.21
- CAT (US) [PROMOTION_ELIGIBLE] rank=88.21
- SNOW (US) [PROMOTION_ELIGIBLE] rank=87.01
- BRK-B (US) [PROMOTION_ELIGIBLE] rank=85.82
- IBM (US) [PROMOTION_ELIGIBLE] rank=85.82
- INTC (US) [PROMOTION_ELIGIBLE] rank=85.82
- … and 15 more

## Sources

- `global_candidates.csv`: present=True status=OK rows=15 age_h=0.03
- `global_opportunity_ranking.csv`: present=True status=OK rows=15 age_h=0.03
- `multi_market_candidates.csv`: present=True status=OK rows=15 age_h=1.18
- `watchlist_candidates.csv`: present=True status=OK rows=53 age_h=1.18

## Governance

- Feeds `tae_watchlist_proposal.py` when queue JSON present
- Does **NOT** write `watchlist.txt`
- Does **NOT** call `buy_position()` or modify BUY/SELL logic
