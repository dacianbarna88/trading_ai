# TAE Actionable Signal Audit

**Mode:** OBSERVABILITY_ONLY | **Generated:** 2026-06-30T13:32:09.811946+00:00

## Summary

| Metric | Value |
|--------|-------|
| total_signals | 25 |
| strong_buy_total | 8 |
| strong_buy_already_held | 8 |
| strong_buy_actionable_new | 0 |
| strong_buy_market_open | 0 |
| strong_buy_market_closed | 0 |
| blocked_by_tae | 0 |
| blocked_by_cash | 0 |
| blocked_by_max_positions | 0 |
| actionable_by_market | 0 |
| **Verdict** | **HELD_ONLY** |

**Recommendation:** STRONG BUY signals exist only for tickers already held — no new entry candidates.

## Runtime

- Market regime: `UNKNOWN`
- Market statuses: `{'US': True, 'EU': True, 'UK': True, 'ASIA': False}`
- Open positions: `8` / `12`
- Cash available: `$12662.3`
- Dynamic trade size: `$0.0`
- TAE action: `SELL_ADVISORY` | block_new_buy: `False`

## Ticker lists

- Already held STRONG BUY: SPY, QQQ, PM, MC.PA, ULVR.L, PG, MU, DIA
- Actionable new: —
- Market closed STRONG BUY: —

## Per-signal classification

| Time | Ticker | Signal | Score | Market | Open | Class | Reason | Shadow |
|------|--------|--------|-------|--------|------|-------|--------|--------|
| 2026-06-30 16:31:17 | SPY | STRONG BUY | 100.0 | US | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | — |
| 2026-06-30 16:31:16 | QQQ | STRONG BUY | 100.0 | US | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | — |
| 2026-06-30 16:31:26 | PM | STRONG BUY | 100.0 | US | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | BUY_ALLOWED |
| 2026-06-30 16:31:18 | MC.PA | STRONG BUY | 80.0 | EU | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | — |
| 2026-06-30 16:31:19 | ULVR.L | STRONG BUY | 80.0 | UK | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | BUY_ALLOWED |
| 2026-06-30 16:31:25 | PG | STRONG BUY | 80.0 | US | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | BUY_ALLOWED |
| 2026-06-30 16:31:24 | MU | STRONG BUY | 80.0 | US | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | BUY_ALLOWED |
| 2026-06-30 16:31:22 | DIA | STRONG BUY | 80.0 | US | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | BUY_ALLOWED |
| 2026-06-30 16:31:15 | HSBA.L | TAKE PROFIT | 40.0 | UK | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 16:31:24 | MRK | WAIT | 40.0 | US | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:18 | SIE.DE | TAKE PROFIT | 40.0 | EU | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 16:31:16 | ALV.DE | TAKE PROFIT | 40.0 | EU | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 16:31:15 | AIR.PA | TAKE PROFIT | 40.0 | EU | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 16:31:23 | ABBV | TAKE PROFIT | 40.0 | US | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 16:31:19 | AAPL | WAIT | 40.0 | US | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:21 | AZN.L | WAIT | 40.0 | UK | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:22 | LLY | WAIT | 40.0 | US | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:26 | GE | TAKE PROFIT | 40.0 | US | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 16:31:23 | AMAT | TAKE PROFIT | 40.0 | US | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 16:31:27 | HD | WAIT | 40.0 | US | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:19 | NVDA | WAIT | 0.0 | US | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:21 | SHEL.L | WAIT | 0.0 | UK | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:20 | MSFT | WAIT | 0.0 | US | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:20 | SAP.DE | WAIT | 0.0 | EU | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 16:31:21 | BP.L | WAIT | 0.0 | UK | True | WAIT | Signal is WAIT — no BUY intent | — |

---
*Canonical runtime constants from live_bot.py; config/settings.py noted in JSON.*
