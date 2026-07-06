# TAE Opportunity Cost Ledger

**Generated:** 2026-07-06T23:41:58
**Mode:** SHADOW_ONLY — NONE
**Global verdict:** OPPORTUNITY_LEDGER_READY

> **SHADOW_ONLY read-only ledger — explains why profit was missed**

## Executive summary

- Total opportunity cost: **$829.72**
- Critical-tier cost: **$685.08**
- Growth capture rate (upstream): **0.2912**
- Recommended top shadow fix: **TEST_CONTEXT_WEIGHT_ADJUSTMENT**
- Ledger entries: **12** (5 top missed)

## Opportunity cost total

**$829.72** aggregate missed USD across 12 tickers with material miss.

## Cost by category

| category | missed USD |
| --- | --- |
| MARKET_CONTEXT_REVERSAL | $685.08 |
| UNKNOWN | $124.42 |
| REENTRY_MISSED | $20.22 |

## Cost by severity

| severity | missed USD |
| --- | --- |
| CRITICAL | $685.08 |
| LOW | $99.00 |
| MEDIUM | $45.64 |

## Top missed opportunities

| ticker | missed USD | category | severity | fix | confidence |
| --- | --- | --- | --- | --- | --- |
| HSBA.L | $235.96 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT | 0.95 |
| MU | $226.61 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT | 0.95 |
| AMAT | $222.51 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT | 0.95 |
| LLY | $45.64 | UNKNOWN | MEDIUM | COLLECT_MORE_DATA | 0.35 |
| PM | $22.25 | UNKNOWN | LOW | COLLECT_MORE_DATA | 0.35 |

## Per-ticker ledger

| ticker | missed | high% | cur% | category | severity | fix | growth |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HSBA.L | $235.96 | 9.22 | -0.22 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT | MISSED_WINNER |
| MU | $226.61 | 9.13 | 0.07 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT | MISSED_WINNER |
| AMAT | $222.51 | 8.95 | 0.05 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT | MISSED_WINNER |
| LLY | $45.64 | 4.51 | 2.69 | UNKNOWN | MEDIUM | COLLECT_MORE_DATA | ACTIVE_WINNER |
| PM | $22.25 | 3.56 | 2.67 | UNKNOWN | LOW | COLLECT_MORE_DATA | CAPTURED_WINNER |
| SPY | $22.02 | 2.27 | 1.39 | UNKNOWN | LOW | COLLECT_MORE_DATA | CAPTURED_WINNER |
| SIE.DE | $20.42 | 0.75 | -0.07 | UNKNOWN | LOW | COLLECT_MORE_DATA | UNKNOWN |
| MC.PA | $10.5 | 0.74 | 0.32 | REENTRY_MISSED | LOW | TEST_REENTRY_POLICY | CAPTURED_WINNER |
| AAPL | $9.72 | 0.26 | -0.13 | REENTRY_MISSED | LOW | TEST_REENTRY_POLICY | UNKNOWN |
| QQQ | $7.86 | 1.54 | -0.98 | UNKNOWN | LOW | COLLECT_MORE_DATA | UNKNOWN |
| PG | $4.47 | 2.17 | 1.99 | UNKNOWN | LOW | COLLECT_MORE_DATA | CAPTURED_WINNER |
| MRK | $1.76 | 1.49 | 1.42 | UNKNOWN | LOW | COLLECT_MORE_DATA | CAPTURED_WINNER |

### Explanations

- **HSBA.L:** HSBA.L: missed $235.96 (peak 9.22%, now -0.22%, drawdown -8.64%). Primary cause: **MARKET_CONTEXT_REVERSAL** — PCE `PROTECT_NOW` signaled context weakening while $235.96 remained at risk. Contributing factors: LATE_PROTECTION, NO_PARTIAL_TAKE_PROFIT, TRAILING_TOO_LOOSE, HOLD_TOO_LONG, PROFIT_GIVEBACK. Growth status: MISSED_WINNER; memory: PROFIT_COLLAPSED.
- **MU:** MU: missed $226.61 (peak 9.13%, now 0.07%, drawdown -8.31%). Primary cause: **MARKET_CONTEXT_REVERSAL** — PCE `CONTEXT_WEAKENING` signaled context weakening while $226.61 remained at risk. Contributing factors: LATE_PROTECTION, NO_PARTIAL_TAKE_PROFIT, TRAILING_TOO_LOOSE, PROFIT_GIVEBACK. Growth status: MISSED_WINNER; memory: PROFIT_COLLAPSED.
- **AMAT:** AMAT: missed $222.51 (peak 8.95%, now 0.05%, drawdown -8.17%). Primary cause: **MARKET_CONTEXT_REVERSAL** — PCE `CONTEXT_WEAKENING` signaled context weakening while $222.51 remained at risk. Contributing factors: LATE_PROTECTION, NO_PARTIAL_TAKE_PROFIT, TRAILING_TOO_LOOSE, PROFIT_GIVEBACK. Growth status: MISSED_WINNER; memory: PROFIT_COLLAPSED.
- **LLY:** LLY: missed $45.64 (peak 4.51%, now 2.69%, drawdown -1.75%). Primary cause: **UNKNOWN** — Insufficient SSOT signals to classify root cause confidently. Growth status: ACTIVE_WINNER; memory: UNKNOWN_OUTCOME.
- **PM:** PM: missed $22.25 (peak 3.56%, now 2.67%, drawdown -0.86%). Primary cause: **UNKNOWN** — Insufficient SSOT signals to classify root cause confidently. Growth status: CAPTURED_WINNER; memory: PROFIT_SURVIVED.

## Recommended shadow fixes

- Top portfolio-wide fix: **TEST_CONTEXT_WEIGHT_ADJUSTMENT**

| category | shadow fix |
| --- | --- |
| CAPITAL_LOCKED | TEST_CAPITAL_ROTATION |
| CASH_CONSTRAINT | TEST_CASH_RESERVE_POLICY |
| EXIT_TOO_EARLY | TEST_HOLD_EXTENSION |
| HOLD_TOO_LONG | TEST_EARLIER_EXIT_GOVERNOR |
| LATE_PROTECTION | TEST_FASTER_PDG_ESCALATION |
| MARKET_CONTEXT_REVERSAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT |
| NO_PARTIAL_TAKE_PROFIT | TEST_PARTIAL_TP_AT_DYNAMIC_THRESHOLD |
| POSITION_LIMIT_CONSTRAINT | TEST_POSITION_SLOT_POLICY |
| PROFIT_GIVEBACK | TEST_EARLIER_PROFIT_LOCK |
| REENTRY_MISSED | TEST_REENTRY_POLICY |
| TRAILING_TOO_LOOSE | TEST_TIGHTER_TRAILING |
| UNKNOWN | COLLECT_MORE_DATA |

## Portfolio policy context

- Source: `tae_adaptive_profit_policy_engine.json`
- Portfolio verdict: **PORTFOLIO_HIGH_RISK**
- Policy state: **HIGH_RISK**
- Suggested shadow policy: **CAPITAL_PRESERVATION_SHADOW**
- Profit quality score: **55.6**

## Recommended next sprint

**X.PROFIT-GROWTH-3 — Winner DNA Profiler**

## Safety confirmation

- SHADOW_ONLY: **true**
- READ_ONLY: **true**
- NO_BROKER: **true**
- NO_LIVE_EXECUTION_CHANGE: **true**
- NO_ADVISORY_CHANGE: **true**
- portfolio.csv modified: **false**

## Sources loaded

- ✅ bot_output.log
- ✅ tae_accounting_snapshot.json
- ✅ tae_adaptive_profit_policy_engine.json
- ✅ tae_intraday_fade_history_summary.md
- ✅ tae_portfolio_profit_governor.json
- ✅ tae_profit_context_engine.json
- ✅ tae_profit_decision_governor.json
- ✅ tae_profit_growth_analytics.json
- ✅ tae_profit_memory_engine.json
- ✅ tae_profit_protection_shadow.json
- ✅ tae_profit_protection_validation.json
- ✅ tae_shadow_validation_events.csv
