# TAE Profit Growth Analytics SSOT — Sprint Report

**Sprint:** X.PROFIT-GROWTH-1 — Profit Growth Analytics SSOT  
**Date:** 2026-07-06  
**Base checkpoint:** `797ced8` — TAE Master governed development workflow  
**Workflow phase:** 0–3 (Audit → Architecture → Shadow Build → Validation)  
**Mode:** SHADOW_ONLY · READ_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE · NO_ADVISORY_CHANGE · NO_COMMIT  
**Status:** **PASS**

---

## Summary

Created the first **Profit Growth Analytics SSOT** — a read-only layer that joins existing accounting, protection shadow, governor, and policy outputs into unified growth metrics. No new decision engine. No live or advisory changes.

---

## Files created

| File | Role |
|------|------|
| `tae_profit_growth_analytics.py` | Analytics engine (stdlib only) |
| `tae_profit_growth_analytics.json` | Structured SSOT output |
| `tae_profit_growth_analytics.md` | Human-readable report |
| `tae_cli/commands/growth_analytics.py` | CLI command |
| `TAE_PROFIT_GROWTH_ANALYTICS_SSOT_REPORT.md` | This report |

**Modified (CLI only):** `tae_cli/dispatcher.py`, `tae_cli/commands/help.py`

**Not modified:** `live_bot.py`, `core/`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt`, advisory modules

---

## Inputs reused (read-only)

| Source | Used for |
|--------|----------|
| `tae_accounting_snapshot.json` | Corrected PnL, account value |
| `tae_profit_protection_shadow.json` | Missed USD, per-ticker peaks |
| `tae_portfolio_profit_governor.json` | Portfolio verdict, quality score |
| `tae_adaptive_profit_policy_engine.json` | Policy state, shadow policy |
| `tae_profit_decision_governor.json` | Governor recommendations |
| `tae_profit_context_engine.json` | PCE verdicts |
| `tae_profit_memory_engine.json` | Memory labels |
| `tae_profit_protection_validation.json` | Validation context |

Optional: fade summary MD, shadow events CSV (loaded flags only)

---

## Metrics created

### Core (portfolio)

| Metric | Live run value |
|--------|----------------|
| `corrected_total_trading_pnl` | 340.91 |
| `corrected_realized_pnl` | 148.33 |
| `corrected_unrealized_pnl` | 192.58 |
| `account_value_corrected` | 30,340.91 |
| `aggregate_missed_usd` | 829.72 |
| `profit_capture_rate` | **0.2912** (29.1%) |
| `opportunity_cost_ratio` | 0.7088 |
| `missed_to_captured_ratio` | 2.43 |
| `profit_quality_score` | 55.6 |
| `portfolio_verdict` | PORTFOLIO_HIGH_RISK |
| `policy_state` | HIGH_RISK |
| `suggested_shadow_policy` | CAPITAL_PRESERVATION_SHADOW |

### Per-ticker

`ticker`, `current_pct`, `high_pct`, `drawdown`, `missed_usd`, `governor_recommendation`, `pce_verdict`, `memory_label`, `growth_status`, `growth_opportunity_score`

**Growth statuses:** CAPTURED_WINNER · MISSED_WINNER · ACTIVE_WINNER · PROFIT_DECAY · WATCHLIST_GROWTH · UNKNOWN

### Global verdict

`GROWTH_ANALYTICS_READY` (accounting + shadow both present)

---

## Sample output highlights

**Top missed winners:** HSBA.L ($235.96), MU ($226.61), AMAT ($222.51) — all MISSED_WINNER (high peak ≥6%, current ≤1%)

**Top active/captured:** PM, PG, MRK, SPY — CAPTURED_WINNER; LLY — ACTIVE_WINNER

**Growth gaps discovered:**

- Low profit capture rate (~29%) — missed dominates captured
- 3 tickers MISSED_WINNER
- Multiple PROFIT_DECAY candidates

---

## Validation

```bash
python3 tae_profit_growth_analytics.py          # PASS
python3 tae.py growth-analytics                 # PASS
python3 tae.py help                             # PASS (includes growth-analytics)
FORBIDDEN_IMPORTS: []                           # PASS
```

---

## Recommended next sprint

```text
X.PROFIT-GROWTH-2 — Opportunity Cost Ledger
```

Persist capture/missed metrics as a time series across runs (APPE + growth analytics history).

---

## Confirmations

| Rule | Status |
|------|--------|
| SHADOW_ONLY | ✅ |
| READ_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_EXECUTION | ✅ |
| NO_PORTFOLIO_CHANGE | ✅ |
| NO_LIVE_BOT_CHANGE | ✅ |
| NO_ADVISORY_CHANGE | ✅ |
| NO_COMMIT | ✅ |

---

## Overall verdict

**PASS** — Profit Growth Analytics SSOT operational. First official Profit Growth sprint complete under master workflow Phase 0–3.
