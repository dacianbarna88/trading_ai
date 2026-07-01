# TAE X.PROTECT-1 — Profit Protection Shadow Engine Report

**Date:** 2026-07-01  
**Sprint:** X.PROTECT-1  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Status:** Implemented — `live_bot.py` unchanged

---

## 1. Problem observed today

Strict audit confirmed the primary issue is **not stock selection** — it is **intraday profit evaporation**:

| Metric | Value |
|--------|-------|
| Current unrealized | **-33.43 USD** |
| Theoretical at high | **+453.34 USD** |
| Missed intraday opportunity | **+486.76 USD** |

Notable cases:

- **MU** — reached `high_pct +5.22%`, then faded negative (`current_pct -0.97%`)
- **PM**, **SIE.DE** — `SIGNIFICANT_INTRADAY_FADE`
- Dangerous cycle observed: **BUY → STOP → BUY → STOP** (research context, not modified live)

Formal TP 5% / SL -3% did not capture intraday peaks. Protection must be **researched in shadow** before any live change.

---

## 2. Why we do NOT modify `live_bot.py`

- No validated production rule yet — only shadow hypotheses
- Changing exits without historical validation risks over-trading
- STOP/TP thresholds remain canonical until X.PROTECT-2+ approval
- This sprint produces **comparison data only**, not orders

---

## 3. Design — SHADOW_ONLY

`tae_profit_protection_shadow.py`:

- Reads open positions from fade intelligence + FIFO from `portfolio.csv`
- Evaluates protection rules per ticker
- Compares estimated outcomes: partial 20%, partial 30%, trailing 1%, trailing 1.5%
- Integrates knowledge base trailing priority when present
- Writes JSON + MD — **never** touches `portfolio.csv`, `live_signals.csv`, or broker

All `reason` fields prefixed with `SHADOW_ONLY`. Actions limited to:

`OBSERVE`, `TEST_SELL_20`, `TEST_SELL_30`, `TEST_TRAILING_1`, `TEST_TRAILING_1_5`

---

## 4. Shadow rules tested

| Signal | Conditions |
|--------|------------|
| `PROFIT_PROTECTION_WATCH` | high_pct ≥ 2, drawdown ≤ -1%, missed > 25 USD |
| `PARTIAL_TAKE_PROFIT_SHADOW_20` | high_pct ≥ 3, drawdown ≤ -1.5%, current_pct > -1 |
| `PARTIAL_TAKE_PROFIT_SHADOW_30` | high_pct ≥ 5, drawdown ≤ -1%, current_pct > -1.5 |
| `TRAILING_PROTECTION_SHADOW` | high_pct ≥ 2, drawdown ≤ -1, trailing best in discovery/knowledge |
| `NO_PROTECTION` | otherwise |

Priority: **30% partial > 20% partial > trailing > watch > none**

Knowledge boost: if `tae_knowledge_base.json` recommends `TEST_TRAILING_SHADOW`, trailing priority increases.

---

## 5. Live results (2026-07-01)

| Summary | Value |
|---------|-------|
| Positions | 12 |
| Partial 20% signals | 1 (LLY) |
| Partial 30% signals | 1 (MU) |
| Trailing signals | 2 (PM, SIE.DE) |
| Watch | 0 |
| Total missed opportunity | **486.76 USD** |
| Best shadow method (portfolio) | **TEST_TRAILING_1** (252.95 USD theoretical) |

Estimated shadow totals:

| Method | Estimated PnL |
|--------|---------------|
| TEST_SELL_20 | 63.92 USD |
| TEST_SELL_30 | 112.60 USD |
| TEST_TRAILING_1 | **252.95 USD** |
| TEST_TRAILING_1_5 | 176.23 USD |

**Verdict:** SHADOW_ONLY — major intraday profit missed; protection shadow review recommended.

---

## 6. Files created

| File | Role |
|------|------|
| `tae_profit_protection_shadow.py` | Shadow protection engine |
| `tae_profit_protection_shadow_test.py` | 11 unit tests |
| `tae_profit_protection_shadow.json` | Structured output |
| `tae_profit_protection_shadow.md` | Human-readable report |

---

## 7. Tests run

```bash
python3 -m py_compile tae_profit_protection_shadow.py
python3 tae_profit_protection_shadow_test.py   # 11/11 OK
python3 tae_profit_protection_shadow.py
python3 -m py_compile live_bot.py tae_intraday_fade_intelligence.py \
  tae_intraday_discovery_engine.py tae_knowledge_base.py
```

Coverage: all 5 rules, confidence tiers, summary totals, knowledge trailing boost, missing files, no live BUY/SELL actions.

---

## 8. Confirmations

| Check | Status |
|-------|--------|
| SHADOW_ONLY | **YES** |
| PAPER_ONLY | **YES** |
| NO_BROKER | **YES** |
| No real BUY/SELL | **YES** |
| `live_bot.py` untouched | **YES** |
| STOP/TP unchanged | **YES** |
| portfolio.csv untouched | **YES** |
| Git commit | **NO** |

---

## 9. Next: X.PROTECT-2

1. **Validation over history** — replay shadow rules on `tae_intraday_fade_history.csv`
2. **Cooldown after STOP** — detect BUY→STOP→BUY cycles; shadow gate before re-entry
3. **Method comparison report** — trailing vs partial vs hold across 30+ days
4. **Dashboard panel** — profit protection shadow signals (read-only)
5. **Promotion gate** — only after shadow outperforms hold baseline consistently

---

*TAE X.PROTECT-1 — profit protection shadow engine. Research only; no execution.*
