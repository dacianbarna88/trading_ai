# TAE Dynamic Profit Target Adapter

**Generated:** 2026-07-07T02:25:02
**Mode:** SHADOW_ONLY — NONE
**Global verdict:** PROFIT_TARGET_ADAPTER_READY

> **SHADOW_ONLY numeric target guidance — no execution, no upstream recompute**

## Executive summary

- Tickers with targets: **12**
- Dominant target mode: **KEEP_GROWING_SHADOW**
- Portfolio target policy: **CAPITAL_PRESERVATION_SHADOW**
- Avg dynamic partial TP: **5.91%**
- Avg dynamic trailing: **0.95%**
- Avg profit lock: **4.0%**
- Capture improvement hint: Portfolio capture rate 29.1% with $830 missed — earlier partial TP (−1%) on high-opportunity tickers may improve capture (shadow hypothesis).

## Baseline target anchors

- Source: `tae_profit_protection_shadow.json rules_v1_config`
- Partial TP levels: **[6.0, 8.0, 10.0]**
- Primary partial TP: **6.0%**
- Profit lock: **4.0%**
- Trailing: **1.0%** / **1.5%**

## Portfolio target policy

- Policy: **CAPITAL_PRESERVATION_SHADOW**
- Dominant mode: **KEEP_GROWING_SHADOW**

| metric | value |
| --- | --- |
| portfolio_target_policy | CAPITAL_PRESERVATION_SHADOW |
| dominant_target_mode | KEEP_GROWING_SHADOW |
| average_dynamic_partial_tp_pct | 5.91 |
| average_dynamic_trailing_pct | 0.95 |
| average_profit_lock_pct | 4.0 |
| expected_capture_improvement_hint | Portfolio capture rate 29.1% with $830 missed — earlier partial TP (−1%) on high-opportunity tickers may improve capture (shadow hypothesis). |
| profit_capture_rate | 0.2912 |
| opportunity_cost_total | 829.72 |

## Top keep-growing targets

| ticker | partial TP | trailing | hold ceiling | urgency |
| --- | --- | --- | --- | --- |
| MRK | 7.5% | 1.2% | 11.5% | LOW |
| PG | 7.5% | 1.2% | 11.5% | LOW |
| PM | 7.5% | 1.2% | 11.5% | LOW |
| SPY | 7.5% | 1.2% | 11.5% | LOW |

## Top protection targets

| ticker | partial TP | partial size | trailing | urgency |
| --- | --- | --- | --- | --- |
| AMAT | 3.5 | 33% | 0.6% | CRITICAL |
| MU | 3.5 | 33% | 0.6% | CRITICAL |
| HSBA.L | None | 50% | 0.7% | CRITICAL |
| QQQ | 4.0 | 33% | 0.7% | CRITICAL |

## Per-ticker target table

| ticker | strategy | partial TP | trailing | lock | ceiling | min cap | size | urgency | conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MRK | KEEP_GROWING_SHADOW | 7.5% | 1.2% | 4.5% | 11.5% | 95.3% | 20% | LOW | 1.0 |
| PG | KEEP_GROWING_SHADOW | 7.5% | 1.2% | 4.5% | 11.5% | 91.7% | 20% | LOW | 1.0 |
| PM | KEEP_GROWING_SHADOW | 7.5% | 1.2% | 4.5% | 11.5% | 75.0% | 20% | LOW | 1.0 |
| SPY | KEEP_GROWING_SHADOW | 7.5% | 1.2% | 4.5% | 11.5% | 70.0% | 20% | LOW | 1.0 |
| MC.PA | HOLD_AND_MONITOR_SHADOW | 6.0% | 0.95% | 4.0% | 1.74% | 43.2% | 25% | MEDIUM | 1.0 |
| LLY | HOLD_AND_MONITOR_SHADOW | 6.0% | 0.95% | 4.0% | 5.51% | 59.6% | 25% | MEDIUM | 1.0 |
| SIE.DE | HOLD_AND_MONITOR_SHADOW | 6.0% | 0.95% | 4.0% | 1.75% | 0.0% | 25% | MEDIUM | 1.0 |
| AAPL | HOLD_AND_MONITOR_SHADOW | 6.0% | 0.95% | 4.0% | 1.26% | 0.0% | 25% | MEDIUM | 1.0 |
| QQQ | PROTECT_PROFIT_SHADOW | 4.0% | 0.7% | 3.5% | 1.54% | 40.0% | 33% | CRITICAL | 1.0 |
| AMAT | TIGHTEN_TRAIL_SHADOW | 3.5% | 0.6% | 3.25% | 5.0% | 0.6% | 33% | CRITICAL | 1.0 |
| MU | TIGHTEN_TRAIL_SHADOW | 3.5% | 0.6% | 3.25% | 5.0% | 0.8% | 33% | CRITICAL | 1.0 |
| HSBA.L | REDUCE_EXPOSURE_SHADOW | — | 0.7% | 3.0% | -0.22% | 0.0% | 50% | CRITICAL | 1.0 |

## What this reuses

- tae_growth_intelligence.json — primary per-ticker scores and recommended_shadow_strategy
- tae_winner_lifecycle_profiler.json — lifecycle confirmation (read-only fallback)
- tae_opportunity_cost_ledger.json — opportunity category/severity context
- tae_profit_protection_shadow.json — static rules_v1_config baseline anchors
- tae_profit_protection_validation.json — portfolio best shadow method bias
- tae_profit_growth_analytics.json — portfolio capture rate for improvement hint
- tae_adaptive_profit_policy_engine.json — portfolio target policy bias
- tae_profit_decision_governor.json — governor alignment context
- tae_accounting_snapshot.json — accounting context flag

## What this does not duplicate

- Does not recompute growth_score, lifecycle_stage, opportunity categories, capture rate, PSP, or shadow PnL simulation. Translates existing SSOT into numeric targets only.

## Safety confirmation

- SHADOW_ONLY: **true**
- READ_ONLY: **true**
- NO_BROKER: **true**
- NO_LIVE_EXECUTION_CHANGE: **true**
- NO_ADVISORY_CHANGE: **true**
- portfolio.csv modified: **false**
- Upstream engines modified: **false**

## Recommended next sprint

**X.PROFIT-GROWTH-6 — Profit Target Policy Learning**
