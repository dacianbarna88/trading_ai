# TAE Global Candidate Queue

**Generated:** 2026-06-30T12:30:22.998660+00:00
**Mode:** CONTROLLED_INTEGRATION
**Safety:** CONTROLLED_INTEGRATION | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE | NO_WATCHLIST_WRITE | NO_BUY_SELL_LOGIC

## Summary

- Total candidates processed: **63**
- Promotion eligible: **0**
- Already held: **4**
- Already in watchlist: **21**
- Market closed: **38**
- Recommended action: **WAIT_FOR_MARKET_OPEN**

## Promotion Queue

**Action:** WAIT_FOR_MARKET_OPEN

### Top 10 promotion eligible

- *(none)*

### Top 25 monitor

- PANW (US) [MARKET_CLOSED] rank=87.08
- V (US) [MARKET_CLOSED] rank=86.48
- MA (US) [MARKET_CLOSED] rank=83.19
- UNH (US) [MARKET_CLOSED] rank=82.3
- AMD (US) [MARKET_CLOSED] rank=82.0
- CAT (US) [MARKET_CLOSED] rank=82.0
- SNOW (US) [MARKET_CLOSED] rank=80.8
- BRK-B (US) [MARKET_CLOSED] rank=79.61
- IBM (US) [MARKET_CLOSED] rank=79.61
- INTC (US) [MARKET_CLOSED] rank=79.61
- … and 15 more

## Sources

- `global_candidates.csv`: present=True status=OK rows=15 age_h=0.02
- `global_opportunity_ranking.csv`: present=True status=OK rows=15 age_h=0.02
- `multi_market_candidates.csv`: present=True status=OK rows=15 age_h=0.15
- `watchlist_candidates.csv`: present=True status=OK rows=53 age_h=0.16

## Governance

- Feeds `tae_watchlist_proposal.py` when queue JSON present
- Does **NOT** write `watchlist.txt`
- Does **NOT** call `buy_position()` or modify BUY/SELL logic
