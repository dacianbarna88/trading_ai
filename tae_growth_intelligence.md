# TAE Growth Intelligence Integrator

**Generated:** 2026-07-06T23:58:33
**Mode:** SHADOW_ONLY — NONE
**Global verdict:** GROWTH_INTELLIGENCE_READY

> **SHADOW_ONLY unified Profit Growth Intelligence — read-only aggregation**

## Executive summary

- Global growth score: **52.7** / 100
- Portfolio growth quality: **55.5**
- Profit capture rate: **0.2912**
- Opportunity cost total: **$829.72**
- Growth risk index: **44.0**
- Recommended portfolio strategy: **PROTECT_PROFIT_SHADOW**
- Tickers integrated: **12**

## Sources loaded

- ✅ bot_output.log
- ✅ tae_accounting_snapshot.json
- ✅ tae_adaptive_profit_policy_engine.json
- ✅ tae_opportunity_cost_ledger.json
- ✅ tae_portfolio_profit_governor.json
- ✅ tae_profit_context_engine.json
- ✅ tae_profit_decision_governor.json
- ✅ tae_profit_growth_analytics.json
- ✅ tae_profit_memory_engine.json
- ✅ tae_profit_protection_shadow.json
- ✅ tae_profit_protection_validation.json
- ✅ tae_shadow_validation_events.csv
- ✅ tae_winner_lifecycle_profiler.json

## Portfolio growth metrics

| metric | value |
| --- | --- |
| global_growth_score | 52.7 |
| portfolio_growth_quality | 55.5 |
| capital_efficiency | 57.6 |
| opportunity_index | 31.3 |
| winner_concentration_pct | 41.7 |
| growth_risk | 44.0 |
| growth_maturity_pct | 16.7 |
| profit_capture_rate | 0.2912 |
| opportunity_cost_total | 829.72 |
| top_growth_candidates | ['MRK', 'PG', 'PM', 'SPY', 'MC.PA'] |
| top_risk_candidates | ['AMAT', 'MU', 'HSBA.L', 'LLY', 'QQQ'] |
| top_missed_winners | ['HSBA.L', 'MU', 'AMAT', 'LLY', 'PM'] |
| recommended_portfolio_shadow_strategy | PROTECT_PROFIT_SHADOW |
| portfolio_verdict | PORTFOLIO_HIGH_RISK |
| policy_state | HIGH_RISK |
| suggested_shadow_policy | CAPITAL_PRESERVATION_SHADOW |

## Top growth candidates

| ticker | growth_score | winner_quality | strategy |
| --- | --- | --- | --- |
| MRK | 94.2 | 100.0 | KEEP_GROWING_SHADOW |
| PG | 94.1 | 100.0 | KEEP_GROWING_SHADOW |
| PM | 87.7 | 95.0 | KEEP_GROWING_SHADOW |
| SPY | 83.9 | 93.8 | KEEP_GROWING_SHADOW |
| MC.PA | 68.2 | 70.5 | HOLD_AND_MONITOR_SHADOW |

## Top risk candidates

| ticker | opportunity | collapse | lifecycle | strategy |
| --- | --- | --- | --- | --- |
| AMAT | 100.0 | 1.0 | PROFIT_DECAY | TIGHTEN_TRAIL_SHADOW |
| MU | 100.0 | 1.0 | PROFIT_DECAY | TIGHTEN_TRAIL_SHADOW |
| HSBA.L | 100.0 | 1.0 | COLLAPSED | REDUCE_EXPOSURE_SHADOW |
| LLY | 19.4 | 0.35 | EARLY_WINNER | HOLD_AND_MONITOR_SHADOW |
| QQQ | 14.0 | 0.817 | WEAKENING | PROTECT_PROFIT_SHADOW |

## Top missed winners

| ticker | missed USD | category | growth_status |
| --- | --- | --- | --- |
| HSBA.L | $235.96 | MARKET_CONTEXT_REVERSAL | MISSED_WINNER |
| MU | $226.61 | MARKET_CONTEXT_REVERSAL | MISSED_WINNER |
| AMAT | $222.51 | MARKET_CONTEXT_REVERSAL | MISSED_WINNER |
| LLY | $45.64 | UNKNOWN | ACTIVE_WINNER |
| PM | $22.25 | UNKNOWN | CAPTURED_WINNER |

## Per-ticker growth intelligence table

| ticker | growth | winner Q | opp | lifecycle | stage | strategy | conf |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MRK | 94.2 | 100.0 | 0.4 | 100.0 | SURVIVED | KEEP_GROWING_SHADOW | 1.0 |
| PG | 94.1 | 100.0 | 1.1 | 100.0 | SURVIVED | KEEP_GROWING_SHADOW | 1.0 |
| PM | 87.7 | 95.0 | 5.6 | 88.8 | EARLY_WINNER | KEEP_GROWING_SHADOW | 1.0 |
| SPY | 83.9 | 93.8 | 5.5 | 84.3 | EARLY_WINNER | KEEP_GROWING_SHADOW | 1.0 |
| MC.PA | 68.2 | 70.5 | 12.6 | 66.8 | DISCOVERY | HOLD_AND_MONITOR_SHADOW | 1.0 |
| LLY | 67.7 | 77.5 | 19.4 | 73.3 | EARLY_WINNER | HOLD_AND_MONITOR_SHADOW | 1.0 |
| SIE.DE | 46.9 | 52.5 | 5.1 | 47.1 | DISCOVERY | HOLD_AND_MONITOR_SHADOW | 1.0 |
| AAPL | 46.1 | 52.5 | 12.4 | 47.4 | DISCOVERY | HOLD_AND_MONITOR_SHADOW | 1.0 |
| QQQ | 30.3 | 21.5 | 14.0 | 16.4 | WEAKENING | PROTECT_PROFIT_SHADOW | 1.0 |
| AMAT | 5.1 | 0.0 | 100.0 | 0.0 | PROFIT_DECAY | TIGHTEN_TRAIL_SHADOW | 1.0 |
| MU | 5.1 | 0.0 | 100.0 | 0.0 | PROFIT_DECAY | TIGHTEN_TRAIL_SHADOW | 1.0 |
| HSBA.L | 3.4 | 0.0 | 100.0 | 0.0 | COLLAPSED | REDUCE_EXPOSURE_SHADOW | 1.0 |

## Recommended shadow strategies

| strategy | count |
| --- | --- |
| KEEP_GROWING_SHADOW | 4 |
| HOLD_AND_MONITOR_SHADOW | 4 |
| TIGHTEN_TRAIL_SHADOW | 2 |
| PROTECT_PROFIT_SHADOW | 1 |
| REDUCE_EXPOSURE_SHADOW | 1 |

## What this reuses

- **tae_profit_growth_analytics.json** — Captured vs missed metrics, growth_status, per-ticker PnL peaks
- **tae_opportunity_cost_ledger.json** — Opportunity cost category, severity, shadow fix mapping
- **tae_winner_lifecycle_profiler.json** — Lifecycle stage, collapse/survival, lifecycle_score
- **tae_profit_memory_engine.json** — Memory labels and episode enrichment
- **tae_profit_context_engine.json** — PCE verdicts and trend context
- **tae_profit_decision_governor.json** — Governor recommendations
- **tae_portfolio_profit_governor.json / tae_adaptive_profit_policy_engine.json** — Portfolio verdict and policy state

## What this does not duplicate

- GII is a meta-aggregator over GA + ledger + lifecycle outputs. It does not recompute capture rates, opportunity categories, or lifecycle stages.

**Reuse decision:** Read upstream JSON artifacts only; no re-import of upstream Python modules

## True remaining gaps

- No critical integration gaps — all three growth layers present

## Recommended next sprint

**X.PROFIT-GROWTH-5 — Dynamic Profit Target Optimizer**

## Safety confirmation

- SHADOW_ONLY: **true**
- READ_ONLY: **true**
- NO_BROKER: **true**
- NO_LIVE_EXECUTION_CHANGE: **true**
- NO_ADVISORY_CHANGE: **true**
- portfolio.csv modified: **false**
