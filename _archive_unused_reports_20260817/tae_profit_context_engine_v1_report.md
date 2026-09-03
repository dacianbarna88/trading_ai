# TAE Profit Context Engine v1 — Implementation Report

**Date:** 2026-07-06  
**Mode:** SHADOW_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE  
**Status:** **PASS**

---

## Summary

Built `tae_profit_context_engine.py` — a shadow-only layer that helps PDC distinguish **normal pullbacks inside strong winners** from **real profit decay requiring protection**. Integrated into `python3 tae.py protect` after committee learning.

---

## Context Model

### Profit Context Score (0–100)

Higher = stronger case to **keep the winner**.  
Lower = stronger case to **protect profit**.

### Context verdicts

| Verdict | Meaning |
|---------|---------|
| `KEEP_WINNER` | Healthy trend + stable profit context |
| `NORMAL_PULLBACK` | Positive PnL with moderate, normal fade |
| `CONTEXT_WEAKENING` | Mixed signals; monitor closely |
| `PROTECT_NOW` | Collapse/decay + high PDC/PSP risk |
| `UNKNOWN_CONTEXT` | Insufficient data |

### Context factors (8)

| Factor | Source |
|--------|--------|
| `trend_context` | live_signals.csv (signal, RSI, SMA50) |
| `market_context` | regime + cross-market summaries |
| `sector_context` | sector intelligence summary |
| `momentum_context` | RSI + signal score |
| `volatility_context` | drawdown magnitude |
| `memory_context` | profit memory episodes/bias |
| `psp_context` | PSP survival/giveback |
| `committee_context` | PDC recommendation + score |

---

## Scoring Rules

**Increases context score:**
- PDC HOLD + PSP survival ≥ 0.70 (+15)
- Memory survived (+12)
- Current PnL > 0, small drawdown (+10)
- Trend healthy (+8), market supportive (+5)
- PSP strong (+10), committee hold (+6)

**Decreases context score:**
- Memory collapsed/decayed (−15/−8)
- High PDC score + high giveback (−20)
- High giveback / low survival (−8 to −15)
- Current PnL ≤ 0 with large prior peak (−18)
- High volatility (−10), committee protect (−10)

**Hard rules:**
- `current_pct ≤ 0` and `high_pct ≥ 4%` → cannot be `KEEP_WINNER`
- Missing context → lower confidence, not forced protect

---

## Sample Outputs

### KEEP_WINNER — MRK (score 100)

```
PDC=HOLD | PSP strong | Memory survived | Trend healthy
→ KEEP_WINNER (HIGH confidence)
```

### PROTECT_NOW — AMAT (score 0)

```
Peak +8.95%, current +0.05%, drawdown −8.17%
Memory collapsed | PSP at risk | PDC partial protect
→ PROTECT_NOW (real decay, not normal pullback)
```

### KEEP_WINNER vs PROTECT_NOW distinction

| Ticker | Current | High | Verdict | Why |
|--------|---------|------|---------|-----|
| PM | +2.67% | +3.56% | KEEP_WINNER | Survived memory, stable drawdown |
| AMAT | +0.05% | +8.95% | PROTECT_NOW | Collapsed from peak, high vol |

---

## Global Summary (current run)

| Metric | Value |
|--------|-------|
| Total tickers | 12 |
| Avg context score | 45.2 |
| KEEP_WINNER | 4 |
| PROTECT_NOW | 7 |
| CONTEXT_WEAKENING | 1 |
| Final verdict | `PCE_SHADOW_READY_FOR_OBSERVATION` |

---

## Files Created / Modified

| File | Change |
|------|--------|
| `tae_profit_context_engine.py` | Context engine |
| `tae_profit_context_engine.json` / `.md` | Outputs |
| `tae_cli/commands/protect.py` | Added PCE step + summary |
| `tae_cli/commands/help.py` | Updated protect description |
| `TAE_PROFIT_CONTEXT_ENGINE_V1_REPORT.md` | This report |

**Not modified:** `live_bot.py`, `core/trades.py`, `portfolio.csv`, broker/execution

---

## Validation

```bash
python3 tae_profit_context_engine.py   # PASS
python3 tae.py protect                 # PASS (6-step pipeline)
FORBIDDEN_IMPORTS: []                  # PASS
```

### Protect pipeline order

1. Profit Protection Shadow  
2. PIB  
3. Memory  
4. Committee  
5. Committee Learning  
6. **Profit Context Engine**  
7. Final summary (context → learning → committee)

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

**PASS** — PCE V1 operational. Context engine distinguishes pullback vs decay for PDC; integrated into protect CLI without live behavior changes.
