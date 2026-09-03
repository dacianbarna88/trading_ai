# TAE Opportunity Attrition Audit

**Generated:** 2026-08-06T12:28:29
**Verdict:** `NO_ECONOMICALLY_HARMFUL_UPSTREAM_BLOCKER_PROVEN`

## 25-Opportunity Attrition Table

| Ticker | Signal | Raw top scores | First causal blocker | Category | Final | Actionable | Terminal reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL | WAIT (40.0) | SKIP_PAPER:20.95, HOLD_PAPER:7.24, BUY_PAPER:4.14 | philosophy | other | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| ABBV | STRONG BUY (80.0) | BUY_PAPER:62.76 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| AIR.PA | WAIT (40.0) | BUY_PAPER:33.52 | philosophy | other | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| ALV.DE | TAKE PROFIT (40.0) | HOLD_PAPER:73.53, SKIP_PAPER:11.06, ROTATE_PAPER:8.05 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| AMAT | WAIT (40.0) | SKIP_PAPER:38.06, BUY_PAPER:28.79 | philosophy | other | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| AZN.L | WAIT (40.0) | SKIP_PAPER:21.06, HOLD_PAPER:7.24, BUY_PAPER:4.14 | philosophy | other | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| BP.L | STRONG BUY (80.0) | BUY_PAPER:62.53 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| DIA | STRONG BUY (80.0) | HOLD_PAPER:37.54, BUY_PAPER:33.78, PROTECT_PAPER:9.48 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| GE | TAKE PROFIT (40.0) | BUY_PAPER:33.52 | philosophy | other | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| HD | STRONG BUY (100.0) | BUY_PAPER:33.95, HOLD_PAPER:29.44, ROTATE_PAPER:8.05 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| HSBA.L | STRONG BUY (100.0) | BUY_PAPER:79.65 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| LLY | STRONG BUY (100.0) | BUY_PAPER:127.58 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| MC.PA | WAIT (40.0) | BUY_PAPER:33.24 | philosophy | other | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| MRK | STRONG BUY (100.0) | BUY_PAPER:130.48 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| MSFT | TAKE PROFIT (40.0) | SKIP_PAPER:21.06, HOLD_PAPER:7.24, BUY_PAPER:4.14 | philosophy | other | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| MU | WAIT (60.0) | SKIP_PAPER:38.06, BUY_PAPER:29.01 | philosophy | other | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| NVDA | STRONG BUY (100.0) | BUY_PAPER:79.95 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| PG | WAIT (0.0) | HOLD_PAPER:95.94, BUY_PAPER:15.64, SKIP_PAPER:11.06 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| PM | STRONG BUY (80.0) | BUY_PAPER:111.65 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| QQQ | STRONG BUY (100.0) | BUY_PAPER:37.85, SKIP_PAPER:18.61 | horizon | growth score | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| SAP.DE | TAKE PROFIT (40.0) | BUY_PAPER:33.52, HOLD_PAPER:29.44, ROTATE_PAPER:8.05 | none_preserved_actionable | other | BUY_PAPER | YES | actionable BUY_PAPER |
| SHEL.L | STRONG BUY (100.0) | BUY_PAPER:79.95 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| SIE.DE | WAIT (60.0) | HOLD_PAPER:38.44, BUY_PAPER:33.72, PROTECT_PAPER:16.38 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| SPY | STRONG BUY (80.0) | HOLD_PAPER:103.2, ROTATE_PAPER:24.15, BUY_PAPER:15.64 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |
| ULVR.L | STRONG BUY (100.0) | BUY_PAPER:79.95 | base_signal_policy | CAPITAL_PRESERVATION / policy_skip | SKIP_PAPER | NO | SKIP_PAPER won scoring |

## policy_skip EV +238 Reproducibility

- Status: **INVALID**
- Prior claim: $238.00
- Clean reproduced gross missed: $294.10
- Clean reproduced net: $290.30
- Reason: Prior +238 used unsupported per-ticker floor ($15) on STRONG BUY SKIP without horizon fills; clean horizon formula yields gross missed $294.10 net $290.30 across 24 SKIP tickers.

