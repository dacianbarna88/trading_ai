# TAE PCE V2 — Adaptive Context Learning Report

**Date:** 2026-07-06  
**Mode:** SHADOW_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE  
**Status:** **PASS**

---

## Summary

Upgraded `tae_profit_context_engine.py` from rigid additive scoring to an **adaptive weighted component model**. Weights persist in `tae_profit_context_learning.json` with conservative adjustments from committee learning.

**Key fix:** Tickers with strong trend/sector/momentum no longer hard-zero when PSP/memory signal decay — e.g. AMAT moved from **0.0 → 51.9** (`CONTEXT_WEAKENING`).

---

## Adaptive Context Model

```
profit_context_score = Σ (component_weight × component_subscore) + structural bonuses
```

Each of 8 components maps to a subscore (0–100). Contributions are explainable per ticker.

### Components

| Component | Default weight |
|-----------|----------------|
| market_context | 0.15 |
| sector_context | 0.15 |
| trend_context | 0.15 |
| momentum_context | 0.15 |
| volatility_context | 0.10 |
| psp_context | 0.15 |
| memory_context | 0.10 |
| committee_context | 0.05 |

### Adjusted weights (current run)

| Component | Default | Adjusted | Reason |
|-----------|---------|----------|--------|
| memory_context | 0.10 | **0.12** | Memory accuracy 100% (+0.02) |
| committee_context | 0.05 | **0.03** | Validation accuracy 33% (−0.02) |
| All others | — | unchanged | Normalized to sum 1.0 |

### Constraints

- Weights normalized to **sum 1.0**
- Min per component: **0.03**
- Max per component: **0.30**
- Conservative adjustments: ±0.01 to 0.02 only
- No live/advisory integration

### Structural support

When ≥2 of trend/sector/momentum subscores ≥ 70:
- Floor on context score (~18–28+) so PSP/memory cannot fully dominate
- Small structural bonus (+4 to +12)

---

## Sample Ticker Explanations

### AMAT — CONTEXT_WEAKENING (51.9) — was 0.0 in v1

| Component | Weight × Subscore | Contribution |
|-----------|-------------------|--------------|
| trend_context | 0.15 × 82 | **12.3** |
| sector_context | 0.15 × 76 | **11.4** |
| momentum_context | 0.15 × 52 | 7.8 |
| psp_context | 0.15 × 36 | 5.4 |
| memory_context | 0.12 × 28 | 3.4 |

Strong trend/sector preserved; memory/PSP penalize but do not zero the score. Verdict `CONTEXT_WEAKENING` (not KEEP_WINNER — tiny +0.05% PnL from +8.95% peak).

### MRK — KEEP_WINNER (88.7)

Memory survived + PSP strong + committee HOLD → high weighted score.

### HSBA.L — PROTECT_NOW (51.9)

Score reflects mixed structure, but **safety rule**: current PnL ≤ 0 + large prior peak + memory collapsed → `PROTECT_NOW` (cannot be KEEP_WINNER).

---

## Global Summary (v2 run)

| Metric | v1 | v2 |
|--------|----|----|
| Avg context score | 45.2 | **67.6** |
| KEEP_WINNER | 4 | 4 |
| PROTECT_NOW | 7 | **1** |
| CONTEXT_WEAKENING | 1 | **5** |
| Verdict | PCE_SHADOW_READY | PCE_SHADOW_READY |

---

## Files Created / Updated

| File | Change |
|------|--------|
| `tae_profit_context_engine.py` | v2 adaptive weighted scoring |
| `tae_profit_context_learning.json` / `.md` | Weight persistence + docs |
| `tae_profit_context_engine.json` / `.md` | Component contributions |
| `tae_cli/commands/protect.py` | Shows context learning summary |
| `TAE_PCE_V2_ADAPTIVE_CONTEXT_REPORT.md` | This report |

**Not modified:** `live_bot.py`, `core/trades.py`, `portfolio.csv`, broker/execution

---

## Validation

```bash
python3 tae_profit_context_engine.py   # PASS
python3 tae.py protect                 # PASS (full pipeline)
FORBIDDEN_IMPORTS: []                  # PASS
```

---

## Live Execution Confirmation

| Check | Status |
|-------|--------|
| BUY/SELL executed | **NO** |
| `live_trading_impact` | `NONE` |
| Broker touched | **NO** |
| Commit | **NO** |

---

## Overall Verdict

**PASS** — PCE V2 adaptive weighted context model operational. Scoring is explainable, weights persist, and rigid zeroing issue resolved while safety rules remain intact.
