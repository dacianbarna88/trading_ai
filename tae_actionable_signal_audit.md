# TAE Actionable Signal Audit

**Mode:** OBSERVABILITY_ONLY | **Generated:** 2026-06-30T11:34:10.213090+00:00

## Summary

| Metric | Value |
|--------|-------|
| total_signals | 25 |
| strong_buy_total | 7 |
| strong_buy_already_held | 3 |
| strong_buy_actionable_new | 0 |
| strong_buy_market_open | 0 |
| strong_buy_market_closed | 4 |
| blocked_by_tae | 0 |
| blocked_by_cash | 0 |
| blocked_by_max_positions | 0 |
| actionable_by_market | 0 |
| **Verdict** | **STRONG_BUY_WAITING_SESSION** |

**Recommendation:** STRONG BUY signal(s) blocked by market session (PG, PM, MU, DIA). Re-run audit after the relevant exchange opens.

## Runtime

- Market regime: `UNKNOWN`
- Market statuses: `{'US': False, 'EU': True, 'UK': True, 'ASIA': False}`
- Open positions: `4` / `12`
- Cash available: `$22662.33`
- Dynamic trade size: `$5665.58`
- TAE action: `SELL_ADVISORY` | block_new_buy: `False`

## Ticker lists

- Already held STRONG BUY: SPY, QQQ, MC.PA
- Actionable new: —
- Market closed STRONG BUY: PG, PM, MU, DIA

## Per-signal classification

| Time | Ticker | Signal | Score | Market | Open | Class | Reason | Shadow |
|------|--------|--------|-------|--------|------|-------|--------|--------|
| 2026-06-30 14:33:45 | SPY | STRONG BUY | 100.0 | US | False | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | — |
| 2026-06-30 14:33:44 | QQQ | STRONG BUY | 100.0 | US | False | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | — |
| 2026-06-30 14:33:50 | PG | STRONG BUY | 100.0 | US | False | STRONG_BUY_MARKET_CLOSED | US market session closed for PG | MARKET_SESSION_FILTER |
| 2026-06-30 14:33:51 | PM | STRONG BUY | 100.0 | US | False | STRONG_BUY_MARKET_CLOSED | US market session closed for PM | MARKET_SESSION_FILTER |
| 2026-06-30 14:33:45 | MC.PA | STRONG BUY | 80.0 | EU | True | STRONG_BUY_ALREADY_HELD | Ticker already in open portfolio positions | — |
| 2026-06-30 14:33:50 | MU | STRONG BUY | 80.0 | US | False | STRONG_BUY_MARKET_CLOSED | US market session closed for MU | MARKET_SESSION_FILTER |
| 2026-06-30 14:33:48 | DIA | STRONG BUY | 80.0 | US | False | STRONG_BUY_MARKET_CLOSED | US market session closed for DIA | MARKET_SESSION_FILTER |
| 2026-06-30 14:33:43 | HSBA.L | TAKE PROFIT | 40.0 | UK | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:44 | ALV.DE | TAKE PROFIT | 40.0 | EU | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:51 | GE | TAKE PROFIT | 40.0 | US | False | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:46 | ULVR.L | WAIT | 40.0 | UK | True | WAIT | Signal is WAIT — no BUY intent | BUY_ALLOWED |
| 2026-06-30 14:33:46 | SIE.DE | TAKE PROFIT | 40.0 | EU | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:43 | AIR.PA | TAKE PROFIT | 40.0 | EU | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:49 | ABBV | TAKE PROFIT | 40.0 | US | False | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:47 | AZN.L | TAKE PROFIT | 40.0 | UK | True | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:49 | LLY | WAIT | 40.0 | US | False | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 14:33:50 | MRK | WAIT | 40.0 | US | False | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 14:33:52 | HD | TAKE PROFIT | 40.0 | US | False | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:49 | AMAT | TAKE PROFIT | 40.0 | US | False | TAKE_PROFIT | Signal is TAKE PROFIT — exit review, not a new BUY | — |
| 2026-06-30 14:33:46 | NVDA | WAIT | 0.0 | US | False | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 14:33:48 | SHEL.L | WAIT | 0.0 | UK | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 14:33:46 | AAPL | WAIT | 0.0 | US | False | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 14:33:47 | MSFT | WAIT | 0.0 | US | False | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 14:33:47 | SAP.DE | WAIT | 0.0 | EU | True | WAIT | Signal is WAIT — no BUY intent | — |
| 2026-06-30 14:33:47 | BP.L | WAIT | 0.0 | UK | True | WAIT | Signal is WAIT — no BUY intent | — |

---
*Canonical runtime constants from live_bot.py; config/settings.py noted in JSON.*
