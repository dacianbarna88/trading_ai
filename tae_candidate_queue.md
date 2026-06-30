# TAE Global Candidate Queue

**Generated:** 2026-06-30T10:59:31.813550+00:00
**Mode:** CONTROLLED_INTEGRATION
**Safety:** CONTROLLED_INTEGRATION | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE | NO_WATCHLIST_WRITE | NO_BUY_SELL_LOGIC

## Summary

- Total candidates processed: **63**
- Promotion eligible: **0**
- Already held: **4**
- Already in watchlist: **21**
- Market closed: **20**
- Recommended action: **WAIT_FOR_MARKET_OPEN**

## Promotion Queue

**Action:** WAIT_FOR_MARKET_OPEN

### Top 10 promotion eligible

- *(none)*

### Top 25 monitor

- PANW (US) [MARKET_CLOSED] rank=80.0
- V (US) [MARKET_CLOSED] rank=80.0
- MA (US) [MARKET_CLOSED] rank=75.0
- AMD (US) [MARKET_CLOSED] rank=70.0
- CAT (US) [MARKET_CLOSED] rank=70.0
- SNOW (US) [MARKET_CLOSED] rank=70.0
- UNH (US) [MARKET_CLOSED] rank=70.0
- BRK-B (US) [MARKET_CLOSED] rank=65.0
- IBM (US) [MARKET_CLOSED] rank=65.0
- INTC (US) [MARKET_CLOSED] rank=65.0
- … and 15 more

## Sources

- `global_candidates.csv`: present=True status=OK rows=15 age_h=0.0
- `global_opportunity_ranking.csv`: present=True status=OK rows=15 age_h=0.0
- `multi_market_candidates.csv`: present=True status=OK rows=15 age_h=0.0
- `watchlist_candidates.csv`: present=True status=OK rows=53 age_h=0.0

## Governance

- Feeds `tae_watchlist_proposal.py` when queue JSON present
- Does **NOT** write `watchlist.txt`
- Does **NOT** call `buy_position()` or modify BUY/SELL logic
