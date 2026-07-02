# TAE X.PROTECT-2 — Historical Profit Protection Validator Report

**Date:** 2026-07-02  
**Sprint:** X.PROTECT-2  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Prior design:** `e5c7984` — TAE performance: add profit growth architecture design

---

## 1. Objective

Validate on **historical fade observations** whether shadow profit-protection strategies would have added value vs holding to current unrealized PnL.

X.PROTECT-1 detects opportunities on today's book; **X.PROTECT-2 aggregates history** and applies G1–G6 gates before any advisory promotion.

---

## 2. Inputs

| Source | Path | Required |
|--------|------|----------|
| Fade history (primary) | `runtime_outputs/tae_intraday_fade_history.csv` | Yes |
| Shadow snapshot | `tae_profit_protection_shadow.json` | Optional (context) |
| Discovery engine | `tae_intraday_discovery_engine.json` | Optional (context) |
| Knowledge base | `tae_knowledge_base.json` | Optional (context) |
| Portfolio | `portfolio.csv` | Optional (not written) |

**Reuse:** `confidence_from_observations()` from `tae_profit_protection_shadow.py`; shadow column schema from `tae_intraday_fade_history.py`.

---

## 3. Outputs

| File | Role |
|------|------|
| `tae_profit_protection_validation.py` | Historical validator |
| `tae_profit_protection_validation_test.py` | 17 unit tests |
| `tae_profit_protection_validation.json` | Structured validation report |
| `tae_profit_protection_validation.md` | Human-readable summary |

---

## 4. Methodology

### Per observation

1. Compute **HOLD baseline** = `(current − avg_price) × shares`
2. Read shadow PnL from CSV columns: `shadow_sell_20`, `shadow_sell_30`, `shadow_trailing_1`, `shadow_trailing_1_5`
3. Compare win/loss/neutral vs HOLD (ε = 0.01 USD)
4. Exclude `DATA_UNAVAILABLE` rows

### Aggregations

- **Portfolio strategy stats** — total, avg, median, win rate, protection efficiency, early-cut risk
- **Ticker breakdown** — per-ticker best strategy, fade count, SHADOW recommendation
- **Classification breakdown** — by fade bucket (HOLD, SIGNIFICANT_INTRADAY_FADE, etc.)
- **Daily breakdown** — per date/run_id missed opportunity and verdict

### Gates G1–G6

| Gate | Criterion | Live result |
|------|-----------|-------------|
| G1 | observations ≥ 30 | **FAIL** (26) |
| G2 | best strategy total > 0 | **PASS** (579.05) |
| G3 | best win rate ≥ 60% | **FAIL** (53.85%) |
| G4 | cut-winners rate ≤ 35% | **PASS** (3.85%) |
| G5 | beats HOLD by positive margin | **PASS** (+616.18 USD) |
| G6 | no ticker > 50% of best total | **PASS** |

**Advisory readiness:** **NOT_READY** (failed G1, G3)

---

## 5. Live results (2026-07-02)

### Dataset health

| Metric | Value |
|--------|-------|
| Observations | **26** |
| Unique days | 2 (2026-06-30 → 2026-07-01) |
| Unique tickers | 12 |
| Data quality | LIMITED |
| Confidence | **LOW** (< 30 obs) |

### Strategy ranking

| Strategy | Total USD | Δ vs HOLD | Win rate | Cut winners |
|----------|-----------|-----------|----------|-------------|
| **shadow_trailing_1** | **579.05** | **+616.18** | 54% | 4% |
| shadow_trailing_1_5 | 421.61 | +458.74 | 54% | 4% |
| shadow_sell_30 | 324.30 | +361.43 | 100% | 0% |
| shadow_sell_20 | 218.97 | +256.10 | 100% | 0% |
| HOLD (baseline) | -37.13 | — | — | — |

**Best strategy:** `shadow_trailing_1` — aligns with X.PROTECT-1 live snapshot (TEST_TRAILING_1).

### Notable tickers

| Ticker | Missed opp. | Fade count | Recommendation |
|--------|-------------|------------|----------------|
| PM | 183.79 USD | 4 | INSUFFICIENT_DATA (per-ticker obs < 3 threshold for some) |
| MU | 269.72 USD | 2 | TEST_TRAILING_SHADOW |
| SIE.DE | 112.60 USD | 2 | TEST_TRAILING_SHADOW |

### Verdict

**PROMISING_BUT_NOT_READY** — trailing shadow strongly beats HOLD on aggregate (+616 USD delta), but sample size and win rate gates not met.

---

## 6. Gates summary

```
G1 FAIL — need 4+ more observations (26/30)
G3 FAIL — trailing win rate 53.85% < 60%
G2, G4, G5, G6 PASS
Advisory readiness: NOT_READY
```

---

## 7. Tests

```bash
python3 -m py_compile tae_profit_protection_validation.py   # OK
python3 tae_profit_protection_validation_test.py            # 17/17 OK
python3 tae_profit_protection_validation.py                 # OK
python3 -m py_compile live_bot.py tae_profit_protection_shadow.py \
  tae_intraday_fade_history.py tae_intraday_discovery_engine.py tae_knowledge_base.py  # OK
```

Coverage: missing history, dataset health, strategy/ticker/classification/daily aggregation, win rate, best strategy, protection efficiency, early-cut risk, gates G1–G6, NOT_READY on small dataset, JSON/MD output, no BUY/SELL recommendations.

---

## 8. Confirmations

| Check | Status |
|-------|--------|
| SHADOW_ONLY | **YES** |
| PAPER_ONLY | **YES** |
| NO_BROKER | **YES** |
| No live BUY/SELL/STOP recommendations | **YES** |
| `live_bot.py` untouched | **YES** |
| `portfolio.csv` untouched | **YES** |
| `live_signals.csv` untouched | **YES** |
| Git commit | **NO** |

---

## 9. Advisory verdict

**Do NOT promote to advisory yet.**

Conditions unmet:

- G1: 26 observations (need ≥ 30)
- G3: trailing win rate 54% (need ≥ 60%)
- Confidence tier: LOW

Partial sell strategies show 100% win rate vs HOLD but **lower total value** than trailing — consistent with protecting fade but leaving money on peak capture for high-fade names (MU, PM).

---

## 10. Recommended next step

1. **Continue observation** — run fade history recorder daily until ≥ 30 observations; re-run X.PROTECT-2.
2. **Proceed to X.COOLDOWN-1** in parallel — BUY→STOP→BUY churn (MU, PM, LLY, MC.PA) is a separate failure mode not fully captured by fade history alone; cooldown audit uses `portfolio.csv` + `live_signals.csv`.
3. **Do NOT build X.PROTECT-3 advisory** until G1–G6 pass on rolling window.

---

*TAE X.PROTECT-2 — historical profit protection validation. Research only; no execution.*
