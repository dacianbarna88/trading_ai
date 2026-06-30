# TAE Intraday Fade Intelligence — Audit & Shadow Design Report

**Date:** 2026-06-24  
**Sprint:** X.INTRADAY  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Status:** Implemented as isolated research module — `live_bot.py` unchanged

---

## 1. Problem observed today

Intraday audit of 11 open positions showed:

| Metric | Value |
|--------|-------|
| Total unrealized (current) | **-68.21 USD** |
| Theoretical at today's high | **+298.48 USD** |
| Missed intraday opportunity | **+366.70 USD** |

Formal risk gates were **not** the blocker:

- No ticker hit **TAKE_PROFIT 5%** on cost basis
- No ticker hit **STOP_LOSS -3%** on cost basis

The dominant pattern was **fade from intraday high** — positions moved favorably intraday, then gave back profit before any formal exit fired.

**Top missed (USD):**

| Ticker | Missed opportunity |
|--------|-------------------|
| PM | 70.41 |
| AZN.L | 67.03 |
| LLY | 63.08 |
| MU | 38.57 |
| MRK | 36.02 |

**Verdict:** The system is not failing on SELL/STOP logic; it is **not observing or acting on intraday peak decay**. This is a research gap, not a live execution bug.

---

## 2. Why we do NOT change `live_bot.py`

Per project guardrails:

- BUY/SELL/Risk/Broker/Trailing thresholds remain canonical
- `STOP_LOSS_PCT = -3%`, `TAKE_PROFIT_PCT = 5%` are unchanged
- No broker calls, no order placement
- Intraday fade is **behavioral observation**, not yet validated as a production rule

Changing live_bot without shadow evidence would:

1. Introduce intraday noise into a daily/signal-driven bot
2. Risk over-trading on partial exits
3. Conflate display/risk price issues with strategy design

This module **learns first**, executes never (in this sprint).

---

## 3. What the module learns

`tae_intraday_fade_intelligence.py` daily observes each open position:

**Price path (today):**

- Open, low, high, current (yfinance `1m` → `5m` → `15m` fallback)

**PnL vs FIFO cost basis:**

- Current PnL ($)
- High PnL ($)
- Missed opportunity ($) = `(high - current) × shares`
- Current % / high % / low %
- Drawdown from high %

**Classification (research labels):**

| Label | Rule |
|-------|------|
| `SIGNIFICANT_INTRADAY_FADE` | missed > 50 USD **and** high_pct > 1% |
| `POTENTIAL_PARTIAL_TAKE_PROFIT` | high_pct ≥ 3% **and** current_pct < high_pct − 1% |
| `RISK_INTRADAY_LOW` | low_pct ≤ −2.5% |
| `WATCH_INTRADAY_FADE` | missed > 25 USD (intermediate watch) |
| `HOLD` | otherwise |
| `DATA_UNAVAILABLE` | no intraday bars |

**Shadow strategy simulations (theoretical only):**

1. SELL 20% at high, hold rest at current
2. SELL 30% at high, hold rest at current
3. Trailing intraday 1% from high
4. Trailing intraday 1.5% from high

These answer: *“If we had reacted to the high, how much would totals improve?”* — without placing orders.

---

## 4. Outputs generated

| Output | Description |
|--------|-------------|
| Console | Summary table + totals + verdict |
| `tae_intraday_fade_intelligence.json` | Full structured report |
| `tae_intraday_fade_intelligence.md` | Human-readable daily snapshot |

**JSON totals include:**

- `total_current_unrealized_usd`
- `total_at_high_usd`
- `total_missed_opportunity_usd`
- `total_shadow_sell_20_at_high_usd`
- `total_shadow_sell_30_at_high_usd`
- `total_shadow_trailing_1pct_usd`
- `total_shadow_trailing_1_5pct_usd`
- `significant_intraday_fade_tickers`
- `daily_verdict`

---

## 5. Tests

`tae_intraday_fade_intelligence_test.py` covers:

| Test | Purpose |
|------|---------|
| `test_fifo_open_position_avg` | FIFO cost basis after partial SELL |
| `test_missed_opportunity_calculation` | `(high - current) × shares` |
| `test_classification_significant_intraday_fade` | missed > 50 + high_pct > 1% |
| `test_no_data_data_unavailable` | missing bars → `DATA_UNAVAILABLE` |
| `test_partial_sell_simulation_math` | 20%/30% at high math |
| `test_analyze_position_fields` | end-to-end row shape |

**Run:**

```bash
python3 -m py_compile tae_intraday_fade_intelligence.py
python3 tae_intraday_fade_intelligence_test.py
python3 tae_intraday_fade_intelligence.py
```

---

## 6. Confirmation: SHADOW_ONLY / PAPER_ONLY / NO_BROKER

| Check | Status |
|-------|--------|
| Modifies `live_bot.py` | **NO** |
| Places orders | **NO** |
| Calls broker API | **NO** |
| Changes STOP/TP thresholds | **NO** |
| Reads `portfolio.csv` only | **YES** |
| Uses yfinance read-only | **YES** |
| Git commit | **NO** (per request) |

Module metadata: `"mode": "SHADOW_ONLY"`, `"live_trading_impact": "NONE"`.

---

## 7. Future evolution (not in scope)

After 5–10 trading days of shadow logs:

1. **Partial take profit at intraday high** — e.g. 20–30% when high_pct ≥ 3% and fade detected
2. **Intraday trailing from high** — 1–1.5% trail as alternative to fixed TP
3. **Re-entry rules** — if fade completes and signal re-confirms
4. **Integration with X.RISK** — separate risk cycle (15s) vs signal cycle (60s), still paper-first
5. **Dashboard panel** — render `tae_intraday_fade_intelligence.json` in command center

All future live changes require: shadow backtest on historical intraday bars + explicit sprint approval.

---

## 8. Files created

```
tae_intraday_fade_intelligence.py
tae_intraday_fade_intelligence_test.py
TAE_INTRADAY_FADE_INTELLIGENCE_REPORT.md
```

Runtime artifacts (generated on run):

```
tae_intraday_fade_intelligence.json
tae_intraday_fade_intelligence.md
```

---

*TAE X.INTRADAY — design-first, shadow-only intraday fade intelligence.*
