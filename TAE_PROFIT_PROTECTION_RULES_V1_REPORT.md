# TAE Profit Protection Rules v1 — Implementation Report

**Date:** 2026-07-06  
**Mode:** SHADOW_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE  
**Status:** **PASS**

---

## Summary

Extended `tae_profit_protection_shadow.py` with **Rules v1** — a read-only advisory layer that evaluates open positions and recommends protective actions without modifying live trading, portfolio, or broker behavior.

---

## Rules Implemented

| # | Rule | Flag / Advisory | Threshold |
|---|------|-----------------|-----------|
| 1 | **Profit Lock** | `PROFIT_LOCK_ACTIVE` | Unrealized PnL ≥ +4% (current or peak) |
| 2 | **Trailing Profit Protection** | `PROFIT_AT_RISK` | After profit lock, peak PnL fades ≥ 1.5% from observed high |
| 3 | **Partial Take Profit Advisory** | `TAKE_PROFIT_PARTIAL_25` | Current PnL ≥ +6% |
| | | `TAKE_PROFIT_PARTIAL_33` | Current PnL ≥ +8% |
| | | `TAKE_PROFIT_PARTIAL_50` | Current PnL ≥ +10% |
| 4 | **Negative PnL Safety** | *(no partial TP flags)* | Partial TP advisories suppressed when PnL ≤ 0 |
| 5 | **Cooldown Advisory** | `REENTRY_COOLDOWN_REQUIRED` | Profitable SELL followed by BUY within 24h (portfolio read-only scan) |

Peak PnL tracking uses `max(current_pnl_pct, high_pct from fade intel, prior shadow run peak)`.

Existing fade-based shadow signals (`PARTIAL_TAKE_PROFIT_SHADOW_*`, `TRAILING_PROTECTION_SHADOW`, etc.) are preserved unchanged.

---

## Files Changed

| File | Change |
|------|--------|
| `tae_profit_protection_shadow.py` | Added Rules v1 engine, portfolio cooldown scan, peak state, enriched outputs |
| `tae_profit_protection_shadow_test.py` | Added 5 unit tests for Rules v1 |
| `tae_profit_protection_shadow.json` | Regenerated with `rules_version: v1` and per-position `rules_v1` blocks |
| `tae_profit_protection_shadow.md` | Regenerated with Rules v1 summary table column |
| `TAE_PROFIT_PROTECTION_RULES_V1_REPORT.md` | This report |

**Not modified (confirmed):**

- `live_bot.py`
- `core/trades.py`
- `portfolio.csv` (read-only)
- Broker / execution modules
- `tae_profit_protection_validation.py` (re-run only; no code changes)

---

## Sample Output

### CLI (`python3 tae_profit_protection_shadow.py`)

```
===== TAE PROFIT PROTECTION SHADOW =====
Mode: SHADOW_ONLY — no live orders
Positions: 12
Missed opportunity: 829.72
Watch / Partial20 / Partial30 / Trailing: 0 1 3 0
Rules v1 lock / at-risk / partial TP / cooldown: 4 4 0 2
Best shadow method: TEST_TRAILING_1
Verdict: SHADOW_ONLY: TAE missed major intraday profit — protection shadow review recommended.
Wrote: tae_profit_protection_shadow.json tae_profit_protection_shadow.md
```

### Rules v1 — HSBA.L (profit lock + at risk)

```json
"rules_v1": {
  "flags": ["PROFIT_LOCK_ACTIVE", "PROFIT_AT_RISK"],
  "primary_flag": "PROFIT_AT_RISK",
  "profit_lock_active": true,
  "profit_at_risk": true,
  "peak_pnl_pct": 9.22,
  "current_pnl_pct": -0.38,
  "fade_from_peak_pct": 9.6,
  "partial_take_profit_advisories": [],
  "reentry_cooldown_required": false
}
```

### Rules v1 — MC.PA (reentry cooldown)

```json
"rules_v1": {
  "flags": ["REENTRY_COOLDOWN_REQUIRED"],
  "reentry_cooldown_required": true,
  "reason": "SHADOW_ONLY: profitable SELL then BUY within 0.0h (cooldown 24h); last sell reason: PROFIT +5.00%"
}
```

### Daily summary (Rules v1 counts)

```
rules_v1_verdict: SHADOW_ONLY rules v1: 4 lock, 4 at-risk, 0 partial TP advisories, 2 reentry cooldown.
```

*(0 partial TP advisories is expected: no open position currently has positive current PnL ≥ 6%.)*

---

## Validation Results

| Command | Result |
|---------|--------|
| `python3 tae_profit_protection_shadow_test.py` | **PASS** — 16/16 tests OK |
| `python3 tae_profit_protection_shadow.py` | **PASS** — exit 0, outputs written |
| `python3 tae_profit_protection_validation.py` | **PASS** — exit 0 (historical X.PROTECT-2 validation unchanged) |

### X.PROTECT-2 historical validation (unchanged scope)

- **Verdict:** `PROMISING_BUT_NOT_READY`
- **Observations:** 108 | **Confidence:** HIGH
- **Best strategy:** `shadow_trailing_1` (total 5601.18 USD simulated)
- **Advisory readiness:** WATCH | Gates passed: false
- **Recommendation:** `DO_NOT_PROMOTE_TO_ADVISORY_YET`, `TEST_TRAILING_SHADOW`

Rules v1 is additive shadow advisory logic; historical validation continues to evaluate prior shadow strategies independently.

---

## Live Trading Confirmation

| Check | Status |
|-------|--------|
| `live_bot.py` modified | **NO** |
| `core/trades.py` modified | **NO** |
| `portfolio.csv` modified | **NO** |
| Broker / execution touched | **NO** |
| BUY/SELL orders placed | **NO** |
| Output mode | `SHADOW_ONLY` |
| `live_trading_impact` | `NONE` |

---

## Overall Verdict

**PASS** — TAE Profit Protection Rules v1 implemented in shadow-only mode. All validation commands succeeded. Live trading behavior unchanged.
