# TAE 10-Day Trading Opportunity Audit

**Mode:** FORENSIC_AUDIT_ONLY | **Window:** 2026-06-20 00:00:00 → 2026-06-29 23:39:04
**Generated:** 2026-06-30T02:39:48.384284

## Executive Summary

- Corrected trading PnL (accounting SSOT): **$395.46**
- BUY opportunities (deduped STRONG BUY score≥80): **11541**
- BUY executed (portfolio.csv): **7**
- BUY executed (alert-cycle matches): **16**
- Actionable opportunities (excl. already held): **28**
- BUY not executed (market closed gate): **16**
- FALSE MARKET CLOSED blocked BUY signals: **13**
- FALSE MARKET CLOSED events: **235**
- Missed profit (evidence-based, alerts max price): **$1,161.63**
- Missed profit (MARKET_CLOSED only): **$565.54**

## A. BUY Execution Audit

Dedup rule: first STRONG BUY (score≥80) per ticker per 60s cycle from `alerts_log.csv`.

| Metric | Value |
|---|---:|
| Opportunities (all STRONG BUY cycles) | 11541 |
| Actionable (new entry, not held) | 28 |
| Executed (portfolio.csv) | 7 |
| Executed (alert matches) | 16 |
| Blocked / skipped | 11525 |
| Actionable execution rate | 25.00% |

### Reason breakdown

- **ALREADY_HELD**: 11497
- **MARKET_CLOSED**: 16
- **OTHER**: 12
- **BUY_EXECUTED**: 16

## B. Market Closed Analysis

- Global log count (`Piața este închisă`): **1130**
- False market closed events: **235**
- False closed total minutes (merged intervals): **285.4**

### Per-market blocked-while-open counts

- **US**: 100
- **EU**: 145
- **UK**: 235

### FALSE MARKET CLOSED intervals (sample)

- 2026-06-24T09:32:00 → 2026-06-24T10:07:14 (35.2 min) markets open: EU, UK, US
- 2026-06-24T10:09:47 → 2026-06-24T10:47:55 (38.1 min) markets open: EU, UK, US
- 2026-06-25T08:00:34 → 2026-06-25T09:33:16 (92.7 min) markets open: EU, UK, US
- 2026-06-25T09:43:56 → 2026-06-25T09:43:56 (0.0 min) markets open: EU, UK, US
- 2026-06-25T09:46:02 → 2026-06-25T09:46:02 (0.0 min) markets open: EU, UK, US
- 2026-06-26T08:00:03 → 2026-06-26T09:59:28 (119.4 min) markets open: EU, UK, US

## C. TOP 20 Missed Profits

- **MC.PA** @ 2026-06-24 10:50:51 | $59.46 | OTHER | price 487.7 → max 499.3
- **MC.PA** @ 2026-06-24 10:52:07 | $58.94 | OTHER | price 487.8 → max 499.3
- **MC.PA** @ 2026-06-24 10:49:36 | $57.10 | OTHER | price 488.15 → max 499.3
- **MC.PA** @ 2026-06-24 10:54:41 | $52.92 | OTHER | price 488.95 → max 499.3
- **MC.PA** @ 2026-06-24 10:55:56 | $52.66 | OTHER | price 489.0 → max 499.3
- **MC.PA** @ 2026-06-24 10:47:52 | $52.14 | MARKET_CLOSED | price 489.1 → max 499.3
- **MC.PA** @ 2026-06-24 10:48:20 | $51.61 | MARKET_CLOSED | price 489.2 → max 499.3
- **MC.PA** @ 2026-06-24 10:46:35 | $50.31 | MARKET_CLOSED | price 489.45 → max 499.3
- **MC.PA** @ 2026-06-24 10:53:22 | $49.27 | OTHER | price 489.65 → max 499.3
- **MC.PA** @ 2026-06-24 10:57:11 | $45.63 | OTHER | price 490.35 → max 499.3
- **MC.PA** @ 2026-06-24 10:58:27 | $45.37 | OTHER | price 490.4 → max 499.3
- **MC.PA** @ 2026-06-24 10:59:44 | $44.85 | OTHER | price 490.5 → max 499.3
- **MC.PA** @ 2026-06-24 10:45:19 | $44.33 | MARKET_CLOSED | price 490.6 → max 499.3
- **MC.PA** @ 2026-06-24 11:01:00 | $44.33 | OTHER | price 490.6 → max 499.3
- **MC.PA** @ 2026-06-24 10:44:03 | $42.78 | MARKET_CLOSED | price 490.9 → max 499.3
- **MC.PA** @ 2026-06-24 11:02:17 | $42.78 | OTHER | price 490.9 → max 499.3
- **MC.PA** @ 2026-06-24 11:04:16 | $42.78 | OTHER | price 490.9 → max 499.3
- **MC.PA** @ 2026-06-24 10:42:47 | $40.97 | MARKET_CLOSED | price 491.25 → max 499.3
- **MC.PA** @ 2026-06-24 10:41:31 | $37.87 | MARKET_CLOSED | price 491.85 → max 499.3
- **MC.PA** @ 2026-06-24 10:40:16 | $33.75 | MARKET_CLOSED | price 492.65 → max 499.3

## D. BUY Execution Rate

- opportunities: 11541
- executed: 16
- rejected: 0
- blocked: 16
- skipped: 11509
- execution_rate_pct: 25.0
- rejection_rate_pct: 99.9393

## E. SELL Audit

- Total SELL count: 7
- Total realized PnL: $60.18
- TAKE_PROFIT: $8.13 (4 trades)
- STOP_LOSS: $52.05 (3 trades)
- TRAILING: $0.00 (0 trades)
- MANUAL_OR_OTHER: $0.00 (0 trades)

## F. Capital Utilization

- cash_available_end: 19954.03
- open_positions_value_end: 10441.4351
- account_value_end: 30395.47
- avg_capital_utilization_pct: 45.27
- idle_capital_pct: 54.73
- idle_samples_under_5pct_invested: 0
- utilization_sample_count: 40
- methodology: 6h snapshots reconstructed from portfolio.csv cash flow; end values from tae_accounting_snapshot.json

## G. Daily PnL

- **2026-06-20** | BUY 0 | SELL 0 | PnL $0.00 | open 5
- **2026-06-21** | BUY 0 | SELL 0 | PnL $0.00 | open 5
- **2026-06-22** | BUY 0 | SELL 0 | PnL $0.00 | open 5
- **2026-06-23** | BUY 1 | SELL 1 | PnL $1.81 | open 5
- **2026-06-24** | BUY 5 | SELL 2 | PnL $31.54 | open 8
- **2026-06-25** | BUY 0 | SELL 1 | PnL $40.30 | open 7
- **2026-06-26** | BUY 1 | SELL 2 | PnL $-13.47 | open 6
- **2026-06-27** | BUY 0 | SELL 0 | PnL $0.00 | open 6
- **2026-06-28** | BUY 0 | SELL 0 | PnL $0.00 | open 6
- **2026-06-29** | BUY 0 | SELL 1 | PnL $0.00 | open 5

## H. Root Cause Ranking

1. **MARKET_CLOSED** — $565.54 — 235 false market-closed log events
2. **MAX_POSITIONS** — $0.00 — BUY blocat MAX_POSITIONS in bot logs / shadow events
3. **RISK_GATE** — $0.00 — Market regime / TAE advisory blocks
4. **STOP_LOSS** — $0.00 — Realized STOP LOSS PnL in portfolio.csv
5. **CASH_UNUSED** — $0.00 — Idle capital ~54.73% avg
6. **INSUFFICIENT_SCORE** — $0.00 — Score threshold / non-STRONG BUY
7. **ALREADY_HELD** — $0.00 — Signals while ticker already in portfolio

## I. Recommendations (advisory only)

1. Remove legacy global 'Piața este închisă' gate; enforce per-ticker session open only (impact: 565.54) — 235 false closed events in logs
2. Ensure bot RUNNING during all open market sessions (market_session_guard not DRY_RUN) (impact: operator_confirmation_required) — market_session_guard.log shows BOT=STOPPED with DRY_RUN=True
3. Persist tae_shadow_validation_events.csv for every BUY evaluation cycle (impact: observability) — Shadow ledger file absent/empty — limits per-signal attribution
4. Archive live_signals.csv history (append-only) for multi-day forensic replay (impact: observability) — live_signals.csv is snapshot-only; alerts_log used as proxy
5. Review STOP_LOSS -3% vs whipsaw on AAPL/SIE.DE/CSCO (impact: 0) — portfolio.csv STOP LOSS rows in window
6. Validate MAX_POSITIONS=12 vs actual cash deployment (~35% utilization) (impact: 0.0) — capital utilization section
7. Log Market sessions OPEN/CLOSED line on every cycle (current code path under-logged) (impact: observability) — 0 'Market sessions OPEN' lines in 10-day logs
8. Deduplicate micro-BUY artifacts (MC.PA $0.03) via MIN_TRADE_USD enforcement audit (impact: 0) — portfolio.csv MC.PA 0.0001 share buy
9. Separate REBALANCE/DEPOSIT rows from trading PnL in daily reports (impact: 0) — portfolio.csv DEPOSIT + REBALANCE simulation rows
10. Operator confirm capital base ($30k vs virtual $10k DEPOSIT) (impact: 0) — tae_accounting_snapshot capital_base_status=NEEDS_OPERATOR_CONFIRMATION

## Data Sources

- `runtime_outputs/bot_output.log`, `bot_output.log`
- `alerts_log.csv` (STRONG BUY history)
- `portfolio.csv` (executed trades)
- `tae_accounting_snapshot.json`
- `market_session_guard.log`

## Limitations

- `live_signals.csv` is snapshot-only; alerts_log used for historical STRONG BUY.
- `tae_shadow_validation_events.csv` not available — per-evaluation TAE attribution incomplete.
- Missed profit uses max subsequent alert price in window (not intraday tick data).
- Log timestamps interpreted as US/Eastern for market calendar cross-check.
