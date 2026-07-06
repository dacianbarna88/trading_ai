# TAE Profit Growth Analytics SSOT

**Generated:** 2026-07-06T23:34:26
**Mode:** SHADOW_ONLY — NONE
**Global verdict:** GROWTH_ANALYTICS_READY

> **SHADOW_ONLY read-only analytics — no live or advisory change**

## Executive summary

- Profit captured (corrected total): **$340.91**
- Profit missed (aggregate): **$829.72**
- Profit capture rate: **0.2912**
- Portfolio verdict: **PORTFOLIO_HIGH_RISK**
- Policy state: **HIGH_RISK** → `CAPITAL_PRESERVATION_SHADOW`
- Tickers analyzed: **12**

## Core metrics

| metric | value |
| --- | --- |
| corrected_total_trading_pnl | 340.908 |
| corrected_realized_pnl | 148.3302 |
| corrected_unrealized_pnl | 192.5778 |
| account_value_corrected | 30340.91 |
| aggregate_missed_usd | 829.72 |
| profit_capture_rate | 0.2912 |
| opportunity_cost_ratio | 0.7088 |
| missed_to_captured_ratio | 2.4339 |
| profit_quality_score | 55.6 |
| portfolio_verdict | PORTFOLIO_HIGH_RISK |
| policy_state | HIGH_RISK |
| suggested_shadow_policy | CAPITAL_PRESERVATION_SHADOW |
| profit_captured_usd | 340.91 |
| profit_missed_usd | 829.72 |
| theoretical_total_usd | 1170.63 |

## Profit capture rate

**0.2912** = $340.908 / ($340.908 + $829.72)

- Opportunity cost ratio: **0.7088**
- Missed-to-captured ratio: **2.4339**

## Captured vs missed profit

| Captured (corrected total) | Missed (shadow) | Theoretical total |
| --- | --- | --- |
| $340.91 | $829.72 | $1170.63 |

## Top missed winners

| ticker | high % | current % | missed USD | growth status |
| --- | --- | --- | --- | --- |
| HSBA.L | 9.22 | -0.22 | 235.96 | MISSED_WINNER |
| MU | 9.13 | 0.07 | 226.61 | MISSED_WINNER |
| AMAT | 8.95 | 0.05 | 222.51 | MISSED_WINNER |

## Top active winners

| ticker | current % | high % | missed USD | growth status |
| --- | --- | --- | --- | --- |
| LLY | 2.69 | 4.51 | 45.64 | ACTIVE_WINNER |
| PM | 2.67 | 3.56 | 22.25 | CAPTURED_WINNER |
| PG | 1.99 | 2.17 | 4.47 | CAPTURED_WINNER |
| MRK | 1.42 | 1.49 | 1.76 | CAPTURED_WINNER |
| SPY | 1.39 | 2.27 | 22.02 | CAPTURED_WINNER |

## Portfolio policy context

- Source: `tae_adaptive_profit_policy_engine.json`
- Portfolio verdict: **PORTFOLIO_HIGH_RISK**
- Policy state: **HIGH_RISK**
- Suggested shadow policy: **CAPITAL_PRESERVATION_SHADOW**
- Profit quality score: **55.6**

## Per-ticker growth table

| ticker | current % | high % | drawdown | missed USD | governor | PCE | memory | status | opp score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL | -0.13 | 0.26 | -0.39 | 9.72 | WATCH | CONTEXT_WEAKENING | UNKNOWN_OUTCOME | UNKNOWN | 3.4 |
| AMAT | 0.05 | 8.95 | -8.17 | 222.51 | PARTIAL_PROTECT_SHADOW | CONTEXT_WEAKENING | PROFIT_COLLAPSED | MISSED_WINNER | 48.4 |
| HSBA.L | -0.22 | 9.22 | -8.64 | 235.96 | TRAIL_PROTECT_SHADOW | PROTECT_NOW | PROFIT_COLLAPSED | MISSED_WINNER | 50.4 |
| LLY | 2.69 | 4.51 | -1.75 | 45.64 | TRAIL_PROTECT_SHADOW | NORMAL_PULLBACK | UNKNOWN_OUTCOME | ACTIVE_WINNER | 14.8 |
| MC.PA | 0.32 | 0.74 | -0.42 | 10.5 | OBSERVE | NORMAL_PULLBACK | UNKNOWN_OUTCOME | CAPTURED_WINNER | 1.5 |
| MRK | 1.42 | 1.49 | -0.07 | 1.76 | HOLD | KEEP_WINNER | PROFIT_SURVIVED | CAPTURED_WINNER | 0.3 |
| MU | 0.07 | 9.13 | -8.31 | 226.61 | PARTIAL_PROTECT_SHADOW | CONTEXT_WEAKENING | PROFIT_COLLAPSED | MISSED_WINNER | 49.0 |
| PG | 1.99 | 2.17 | -0.17 | 4.47 | HOLD | KEEP_WINNER | PROFIT_SURVIVED | CAPTURED_WINNER | 0.7 |
| PM | 2.67 | 3.56 | -0.86 | 22.25 | HOLD | KEEP_WINNER | PROFIT_SURVIVED | CAPTURED_WINNER | 3.3 |
| QQQ | -0.98 | 1.54 | -2.47 | 7.86 | WATCH | CONTEXT_WEAKENING | UNKNOWN_OUTCOME | UNKNOWN | 7.6 |
| SIE.DE | -0.07 | 0.75 | -0.81 | 20.42 | WATCH | CONTEXT_WEAKENING | UNKNOWN_OUTCOME | UNKNOWN | 5.0 |
| SPY | 1.39 | 2.27 | -0.86 | 22.02 | HOLD | KEEP_WINNER | UNKNOWN_OUTCOME | CAPTURED_WINNER | 3.2 |

## True growth gaps discovered

- Low profit capture rate — missed opportunity dominates captured PnL
- 3 tickers classified as MISSED_WINNER

## Recommended next sprint

**X.PROFIT-GROWTH-2 — Opportunity Cost Ledger**

## Safety confirmation

- SHADOW_ONLY: **true**
- READ_ONLY: **true**
- NO_BROKER: **true**
- NO_LIVE_EXECUTION_CHANGE: **true**
- NO_ADVISORY_CHANGE: **true**
- portfolio.csv modified: **false**

## Sources loaded

- ✅ tae_accounting_snapshot.json
- ✅ tae_adaptive_profit_policy_engine.json
- ✅ tae_intraday_fade_history_summary.md
- ✅ tae_portfolio_profit_governor.json
- ✅ tae_profit_context_engine.json
- ✅ tae_profit_decision_governor.json
- ✅ tae_profit_memory_engine.json
- ✅ tae_profit_protection_shadow.json
- ✅ tae_profit_protection_validation.json
- ✅ tae_shadow_validation_events.csv
