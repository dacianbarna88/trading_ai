# TAE Winner Lifecycle Profiler

**Generated:** 2026-07-06T23:46:44
**Mode:** SHADOW_ONLY — NONE
**Global verdict:** LIFECYCLE_PROFILER_READY

> **SHADOW_ONLY research layer — how winners are born, grow, weaken, and die**

## Executive summary

- Tickers profiled: **12**
- Portfolio lifecycle score: **43.8** / 100
- Average lifecycle score: **52.0**
- Average survival probability: **0.517**
- Average collapse probability: **0.524**
- Healthy winners: **8** | Weakening: **1** | Collapsing: **2** | Collapsed: **1** | Survived: **2**

## Lifecycle distribution

| stage | count |
| --- | --- |
| COLLAPSED | 1 |
| DISCOVERY | 3 |
| EARLY_WINNER | 3 |
| PROFIT_DECAY | 2 |
| SURVIVED | 2 |
| WEAKENING | 1 |

## Healthy winners

| ticker | stage | score | survival | action |
| --- | --- | --- | --- | --- |
| MRK | SURVIVED | 100.0 | 1.0 | KEEP |
| PG | SURVIVED | 100.0 | 1.0 | KEEP |
| PM | EARLY_WINNER | 88.8 | 1.0 | KEEP |
| SPY | EARLY_WINNER | 84.3 | 0.952 | KEEP |
| LLY | EARLY_WINNER | 73.3 | 0.428 | TRAIL |
| MC.PA | DISCOVERY | 66.8 | 0.879 | WATCH |
| AAPL | DISCOVERY | 47.4 | 0.234 | WATCH |
| SIE.DE | DISCOVERY | 47.1 | 0.218 | WATCH |

## Weakening winners

| ticker | stage | collapse | decay vel | action |
| --- | --- | --- | --- | --- |
| QQQ | WEAKENING | 0.817 | 6.0799 | WATCH |

## Collapsed winners

| ticker | peak % | current % | collapse | missed USD |
| --- | --- | --- | --- | --- |
| HSBA.L | 9.22 | -0.22 | 1.0 | $235.96 |

## Top survivors

| ticker | stage | survival | score |
| --- | --- | --- | --- |
| MRK | SURVIVED | 1.0 | 100.0 |
| PG | SURVIVED | 1.0 | 100.0 |
| PM | EARLY_WINNER | 1.0 | 88.8 |
| SPY | EARLY_WINNER | 0.952 | 84.3 |
| MC.PA | DISCOVERY | 0.879 | 66.8 |

## Top collapse candidates

| ticker | stage | collapse | missed USD | action |
| --- | --- | --- | --- | --- |
| AMAT | PROFIT_DECAY | 1.0 | $222.51 | PARTIAL_PROTECT |
| MU | PROFIT_DECAY | 1.0 | $226.61 | PARTIAL_PROTECT |
| HSBA.L | COLLAPSED | 1.0 | $235.96 | EXIT |
| QQQ | WEAKENING | 0.817 | $7.86 | WATCH |

## Portfolio lifecycle score

**43.8** / 100 (portfolio-weighted health index)


## Recommended shadow actions

| ticker | action | confidence |
| --- | --- | --- |
| AAPL | WATCH | 0.81 |
| AMAT | PARTIAL_PROTECT | 0.56 |
| HSBA.L | EXIT | 0.5 |
| LLY | TRAIL | 0.82 |
| MC.PA | WATCH | 0.66 |
| MRK | KEEP | 0.57 |
| MU | PARTIAL_PROTECT | 0.56 |
| PG | KEEP | 0.58 |
| PM | KEEP | 0.6 |
| QQQ | WATCH | 0.62 |
| SIE.DE | WATCH | 0.8 |
| SPY | KEEP | 0.64 |

## Per-ticker profiles

| ticker | stage | cur% | peak% | score | collapse | survival | action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MRK | SURVIVED | 1.42 | 1.49 | 100.0 | 0.205 | 1.0 | KEEP |
| PG | SURVIVED | 1.99 | 2.17 | 100.0 | 0.22 | 1.0 | KEEP |
| PM | EARLY_WINNER | 2.67 | 3.56 | 88.8 | 0.3 | 1.0 | KEEP |
| SPY | EARLY_WINNER | 1.39 | 2.27 | 84.3 | 0.341 | 0.952 | KEEP |
| LLY | EARLY_WINNER | 2.69 | 4.51 | 73.3 | 0.35 | 0.428 | TRAIL |
| MC.PA | DISCOVERY | 0.32 | 0.74 | 66.8 | 0.35 | 0.879 | WATCH |
| AAPL | DISCOVERY | -0.13 | 0.26 | 47.4 | 0.35 | 0.234 | WATCH |
| SIE.DE | DISCOVERY | -0.07 | 0.75 | 47.1 | 0.35 | 0.218 | WATCH |
| QQQ | WEAKENING | -0.98 | 1.54 | 16.4 | 0.817 | 0.151 | WATCH |
| AMAT | PROFIT_DECAY | 0.05 | 8.95 | 0.0 | 1.0 | 0.173 | PARTIAL_PROTECT |
| HSBA.L | COLLAPSED | -0.22 | 9.22 | 0.0 | 1.0 | 0.0 | EXIT |
| MU | PROFIT_DECAY | 0.07 | 9.13 | 0.0 | 1.0 | 0.168 | PARTIAL_PROTECT |

### Explanations (top collapse candidates)

- **AMAT:** AMAT lifecycle=PROFIT_DECAY: Winner dying — severe giveback (>5% drawdown from peak). Current 0.05% vs peak 8.95% (drawdown -8.17%). Growth velocity 0.123%/day, decay velocity 20.110%/day. Collapse prob 1.00, survival prob 0.17. Memory=PROFIT_COLLAPSED, PCE=CONTEXT_WEAKENING. Optimal shadow action (no execution): PARTIAL_PROTECT.
- **MU:** MU lifecycle=PROFIT_DECAY: Winner dying — severe giveback (>5% drawdown from peak). Current 0.07% vs peak 9.13% (drawdown -8.31%). Growth velocity 0.172%/day, decay velocity 20.455%/day. Collapse prob 1.00, survival prob 0.17. Memory=PROFIT_COLLAPSED, PCE=CONTEXT_WEAKENING. Optimal shadow action (no execution): PARTIAL_PROTECT.
- **HSBA.L:** HSBA.L lifecycle=COLLAPSED: Winner dead — flat or negative after a >6% peak. Current -0.22% vs peak 9.22% (drawdown -8.64%). Growth velocity -0.541%/day, decay velocity 21.267%/day. Collapse prob 1.00, survival prob 0.00. Memory=PROFIT_COLLAPSED, PCE=PROTECT_NOW. Optimal shadow action (no execution): EXIT.
- **QQQ:** QQQ lifecycle=WEAKENING: Winner weakening — drawdown exceeds 2% from peak. Current -0.98% vs peak 1.54% (drawdown -2.47%). Growth velocity -2.412%/day, decay velocity 6.080%/day. Collapse prob 0.82, survival prob 0.15. Memory=UNKNOWN_OUTCOME, PCE=CONTEXT_WEAKENING. Optimal shadow action (no execution): WATCH.

## Recommended next sprint

**X.PROFIT-GROWTH-4 — Dynamic Profit Target Optimizer**

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
- ✅ tae_opportunity_cost_ledger.json
- ✅ tae_portfolio_profit_governor.json
- ✅ tae_profit_context_engine.json
- ✅ tae_profit_decision_governor.json
- ✅ tae_profit_growth_analytics.json
- ✅ tae_profit_memory_engine.json
- ✅ tae_profit_protection_shadow.json
- ✅ tae_profit_protection_validation.json
- ✅ tae_shadow_validation_events.csv
