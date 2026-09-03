# TAE Decision Event Bus (DPE-1)

**Generated:** 2026-09-03T13:15:06+00:00
**Mode:** SHADOW_ONLY — READ_ONLY
**Schema version:** dpe.decision_event.v1

> **Immutable decision events — no execution, no live behavior change**

## Executive summary

- Events built this run: **23**
- Events appended: **0** (skipped duplicates in run: **23**)
- Event log: `runtime_outputs/dpe/decision_events.jsonl`
- Portfolio snapshots: **1**
- Ticker decision snapshots: **22**

## Schema version

`dpe.decision_event.v1` — see `tae_decision_event_bus_schema.json`

## Events generated

| event_type | count |
| --- | --- |
| PORTFOLIO_SNAPSHOT | 1 |
| TICKER_DECISION_SNAPSHOT | 22 |

## Source status

| source | loaded |
| --- | --- |
| bot_output.log | ✅ |
| live_signals.csv | ✅ |
| portfolio.csv | ✅ |
| tae_accounting_snapshot.json | ✅ |
| tae_adaptive_profit_policy_engine.json | ✅ |
| tae_growth_intelligence.json | ✅ |
| tae_market_philosophy_lab.json | ✅ |
| tae_portfolio_profit_governor.json | ✅ |
| tae_profit_context_engine.json | ✅ |
| tae_profit_decision_governor.json | ✅ |
| tae_profit_memory_engine.json | ✅ |
| tae_profit_target_adapter.json | ✅ |

## Portfolio event summary

- Event ID: `20260903_PORTFOLIO_PORTFOLIO_SNAPSHOT_8dcdf8ee43bb0879`
- Account value: **30382.07**
- Winning philosophy: **COLLABORATIVE_MODEL**
- Portfolio verdict: **PORTFOLIO_HIGH_RISK**

## Ticker event summary

| ticker | growth | strategy | philosophy pref |
| --- | --- | --- | --- |
| AAPL | 54.7 | HOLD_AND_MONITOR_SHADOW | COLLABORATIVE |
| ABBV | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| AIR.PA | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| ALV.DE | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| AMAT | 5.1 | TIGHTEN_TRAIL_SHADOW | MIXED |
| DIA | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| GE | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| HD | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| HSBA.L | 3.4 | REDUCE_EXPOSURE_SHADOW | AVOID |
| LLY | 75.2 | KEEP_GROWING_SHADOW | COLLABORATIVE |
| MC.PA | 68.4 | HOLD_AND_MONITOR_SHADOW | COLLABORATIVE |
| MRK | 92.8 | KEEP_GROWING_SHADOW | COLLABORATIVE |
| MU | 5.1 | TIGHTEN_TRAIL_SHADOW | MIXED |
| NVDA | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| PG | 92.4 | KEEP_GROWING_SHADOW | COLLABORATIVE |
| PM | 83.6 | KEEP_GROWING_SHADOW | COLLABORATIVE |
| QQQ | 30.3 | PROTECT_PROFIT_SHADOW | COLLABORATIVE |
| SAP.DE | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| SHEL.L | 32.8 | HOLD_AND_MONITOR_SHADOW | None |
| SIE.DE | 47.4 | HOLD_AND_MONITOR_SHADOW | COLLABORATIVE |
| … | +2 more | | |

## Event log path

`runtime_outputs/dpe/decision_events.jsonl`

## How this feeds DPE-2

DPE-2 Execution Splitter will read `decision_events.jsonl`, fan out each `TICKER_DECISION_SNAPSHOT` into competitive and collaborative decision packets without modifying live execution.

## What this reuses

- tae_accounting_snapshot.json — account_snapshot
- tae_growth_intelligence.json — growth_snapshot per ticker
- tae_profit_target_adapter.json — target_snapshot per ticker
- tae_market_philosophy_lab.json — philosophy_snapshot
- tae_portfolio_profit_governor.json — portfolio_policy_snapshot
- tae_adaptive_profit_policy_engine.json — policy_state
- tae_profit_context_engine.json — risk pce enrichment
- tae_profit_decision_governor.json — governor in risk_snapshot
- live_signals.csv — signal_snapshot
- portfolio.csv — position_snapshot
- bot_output.log — market_session_state hint

## What this does not duplicate

- Does not recompute GII, targets, philosophy scores, accounting, or protection logic. Normalizes existing artifacts into immutable event records for DPE-2 splitter.

## Safety confirmation

- READ_ONLY: **true**
- SHADOW_ONLY: **true**
- NO_BROKER: **true**
- NO_EXECUTION: **true**
- NO_LIVE_BOT_CHANGE: **true**
- NO_ADVISORY_CHANGE: **true**
- portfolio.csv modified: **false**

## Recommended next sprint

**TAE DPE-2 — Execution Splitter**
