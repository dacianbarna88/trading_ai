# TAE Opportunity Cost Ledger V1 — Sprint Report

**Sprint:** X.PROFIT-GROWTH-2 — Opportunity Cost Ledger  
**Date:** 2026-07-06  
**Base checkpoint:** `2d46a35` — TAE Growth 1: add profit growth analytics SSOT  
**Mode:** SHADOW_ONLY · READ_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE · NO_ADVISORY_CHANGE · NO_COMMIT  
**Status:** **PASS**

---

## Summary

Created a read-only **Opportunity Cost Ledger** that classifies **why** profit was missed per ticker, joining growth analytics with protection shadow, governor, context, memory, and policy SSOT inputs. No decision engine, broker, or live changes.

---

## Files created

| File | Role |
|------|------|
| `tae_opportunity_cost_ledger.py` | Ledger engine + classification (stdlib only) |
| `tae_opportunity_cost_ledger.json` | Structured ledger output |
| `tae_opportunity_cost_ledger.md` | Human-readable report |
| `tae_cli/commands/opportunity.py` | CLI command |
| `TAE_OPPORTUNITY_COST_LEDGER_V1_REPORT.md` | This report |

**Modified (CLI only):** `tae_cli/dispatcher.py`, `tae_cli/commands/help.py`

**Not modified:** `live_bot.py`, `core/`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt`, advisory modules

---

## Inputs reused (read-only)

| Source | Used for |
|--------|----------|
| `tae_profit_growth_analytics.json` | Ticker rows, capture rate, growth status |
| `tae_profit_protection_shadow.json` | Partial TP evidence, re-entry flags, missed USD |
| `tae_profit_decision_governor.json` | Governor recommendations (via growth join) |
| `tae_profit_context_engine.json` | PCE verdicts |
| `tae_profit_memory_engine.json` | Memory labels |
| `tae_portfolio_profit_governor.json` | Portfolio verdict, constraint hints |
| `tae_adaptive_profit_policy_engine.json` | Policy state, shadow policy |
| `tae_accounting_snapshot.json` | Cash context for constraints |
| `tae_profit_protection_validation.json` | Validation constraint hints |

Optional: fade summary MD, shadow events CSV, bot_output.log (presence flags only)

---

## Ledger model

### Per-ticker fields

`ticker`, `missed_usd`, `high_pct`, `current_pct`, `drawdown`, `growth_status`, `governor_recommendation`, `pce_verdict`, `memory_label`, `portfolio_verdict`, `policy_state`, `opportunity_cost_category`, `contributing_causes`, `opportunity_cost_severity`, `recommended_shadow_fix`, `confidence`, `explanation`

### Global summary

`total_opportunity_cost_usd`, `critical_cost_usd`, `top_5_cost_tickers`, `cost_by_category`, `cost_by_severity`, `recommended_top_fix`, `portfolio_policy_context`, `global_verdict`

### Categories (12)

PROFIT_GIVEBACK · LATE_PROTECTION · NO_PARTIAL_TAKE_PROFIT · TRAILING_TOO_LOOSE · EXIT_TOO_EARLY · HOLD_TOO_LONG · REENTRY_MISSED · CAPITAL_LOCKED · POSITION_LIMIT_CONSTRAINT · CASH_CONSTRAINT · MARKET_CONTEXT_REVERSAL · UNKNOWN

### Severity thresholds

| Tier | missed_usd |
|------|------------|
| CRITICAL | ≥ 200 |
| HIGH | ≥ 75 |
| MEDIUM | ≥ 25 |
| LOW | < 25 |

---

## Classification logic

Priority-ordered primary cause selection (first matching wins):

1. Portfolio constraints — CASH / POSITION_LIMIT / CAPITAL_LOCKED from PPG/validation/accounting hints  
2. MARKET_CONTEXT_REVERSAL — PCE `PROTECT_NOW` or `CONTEXT_WEAKENING` + missed ≥ $75  
3. LATE_PROTECTION — peak ≥ 6%, missed ≥ $75, governor PARTIAL/TRAIL/PROTECT  
4. NO_PARTIAL_TAKE_PROFIT — peak ≥ 6%, missed ≥ $25, no partial capture evidence in shadow  
5. TRAILING_TOO_LOOSE — drawdown ≤ −5%, missed ≥ $75  
6. HOLD_TOO_LONG — current ≤ 0%, peak ≥ 4%, missed ≥ $25  
7. PROFIT_GIVEBACK — peak ≥ 6%, current ≤ 1%  
8. REENTRY_MISSED — shadow `reentry_cooldown_required`  
9. EXIT_TOO_EARLY — moderate peak gap with collapsed memory  
10. UNKNOWN — insufficient signals  

Each ticker also records `contributing_causes` for multi-factor explanation. Shadow fix mapped 1:1 from primary category.

---

## Sample output

| Metric | Value |
|--------|-------|
| Global verdict | `OPPORTUNITY_LEDGER_READY` |
| Total opportunity cost | $829.72 |
| Critical-tier cost | $685.08 |
| Recommended top fix | `TEST_CONTEXT_WEIGHT_ADJUSTMENT` |

**Top missed (classified):**

| Ticker | Missed | Category | Severity | Fix |
|--------|--------|----------|----------|-----|
| HSBA.L | $235.96 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT |
| MU | $226.61 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT |
| AMAT | $222.51 | MARKET_CONTEXT_REVERSAL | CRITICAL | TEST_CONTEXT_WEIGHT_ADJUSTMENT |

**Cost by category:** MARKET_CONTEXT_REVERSAL $685.08 · UNKNOWN $124.42 · REENTRY_MISSED $20.22

**Insight:** Top three missed winners share PCE weakening + late protection + no partial TP evidence — context reversal is the primary classified cause; contributing factors include LATE_PROTECTION and NO_PARTIAL_TAKE_PROFIT.

---

## Validation

```bash
python3 tae_opportunity_cost_ledger.py          # PASS
python3 tae.py opportunity                      # PASS
python3 tae.py help                             # PASS (includes opportunity)
FORBIDDEN_IMPORTS: []                           # PASS
```

---

## Recommended next sprint

```text
X.PROFIT-GROWTH-3 — Winner DNA Profiler
```

Profile shared traits of MISSED_WINNER vs CAPTURED_WINNER tickers using ledger + growth analytics history.

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

**PASS** — Opportunity Cost Ledger V1 operational. Explains why $829.72 was missed with per-ticker root-cause classification and shadow fix recommendations.
