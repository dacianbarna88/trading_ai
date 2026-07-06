# TAE Profit Intelligence Brain v2 — PSP Report

**Date:** 2026-07-06  
**Checkpoint:** 7f419f2 — TAE PIB V1  
**Mode:** SHADOW_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE  
**Status:** **PASS**

---

## Summary

Extended `tae_profit_intelligence_brain.py` with **Profit Survival Probability (PSP)** — a shadow-only model that estimates whether current profit survives the next session and adjusts PIB v1 recommendations accordingly.

---

## Files Changed

| File | Change |
|------|--------|
| `tae_profit_intelligence_brain.py` | Added `compute_psp()`, `adjust_recommendation_with_psp()`, v2 schema |
| `tae_profit_intelligence_brain.json` | Regenerated with PSP fields per position |
| `tae_profit_intelligence_brain.md` | Regenerated with PSP summary tables |
| `TAE_PROFIT_INTELLIGENCE_BRAIN_V2_PSP_REPORT.md` | This report |

**Not modified:** `live_bot.py`, `core/trades.py`, `portfolio.csv`, broker/execution.

---

## PSP Logic

### Metrics (per position)

| Metric | Description | Range |
|--------|-------------|-------|
| `psp_survival_probability` | Probability current profit survives next session | 0.0–1.0 |
| `psp_giveback_risk` | Probability of giving back ≥50% of peak profit | 0.0–1.0 |
| `psp_protection_urgency` | Protection priority | LOW / MEDIUM / HIGH / CRITICAL |

### Inputs

- `current_pct`, `high_pct`, drawdown, `missed_usd`
- PIB v1 votes: trend, decay, volatility, memory
- Existing PIB v1 recommendation

### Core rules

1. **PnL ≤ 0** → survival = 0; no take-profit escalation (WATCH/NO_ACTION only).
2. **Retention model** → survival base = 0.30 + 0.50 × (current / high), adjusted by trend/decay/volatility votes.
3. **Giveback model** → rises with fade-from-peak; if `high_pct ≥ 6%` and drawdown ≥ 5%, giveback boosted (HIGH/CRITICAL).
4. **Memory boost** → if validation memory supports protection and decay is elevated, urgency increases one level.
5. **Small profit guard** → if `0 < current_pct < 2%`, cap at WATCH (never EXIT).
6. **PSP adjustment** → may escalate (CRITICAL → PARTIAL/EXIT) or de-escalate (high survival → TRAIL/WATCH) vs PIB v1.

### Global verdicts

| Verdict | Condition |
|---------|-----------|
| `PSP_SHADOW_READY_FOR_OBSERVATION` | Shadow + validation loaded; positions evaluated |
| `PSP_SHADOW_NEEDS_MORE_DATA` | High UNKNOWN vote ratio |
| `PSP_NOT_READY` | Missing shadow snapshot |

---

## Validation Output

### Command

```bash
python3 tae_profit_intelligence_brain.py
```

### CLI result

```
===== TAE PROFIT INTELLIGENCE BRAIN v2 (PSP) =====
Mode: SHADOW_ONLY — no live orders
Final verdict: PSP_SHADOW_READY_FOR_OBSERVATION
Positions: 12
Avg survival: 0.406
Avg giveback risk: 0.737
Urgent positions: 5
PSP-adjusted HOLD / WATCH / TRAIL / PARTIAL / EXIT / NO_ACTION: 4 5 0 0 1 2
Total missed USD: 829.72
```

### Artifact checks

| Check | Result |
|-------|--------|
| `tae_profit_intelligence_brain.json` | **EXISTS** |
| `tae_profit_intelligence_brain.md` | **EXISTS** |
| `live_bot.py` changed | **NO** |
| `core/trades.py` changed | **NO** |
| `portfolio.csv` changed | **NO** |

---

## Sample Recommendations

### MU — PIB EXIT → PSP WATCH

Peak +9.13%, current +0.07%, giveback 0.90, CRITICAL urgency. Small positive profit rule downgrades EXIT to WATCH.

```json
{
  "ticker": "MU",
  "current_pct": 0.07,
  "high_pct": 9.13,
  "psp_survival_probability": 0.0,
  "psp_giveback_risk": 0.9,
  "psp_protection_urgency": "CRITICAL",
  "existing_pib_recommendation": "EXIT_PROTECT_SHADOW",
  "psp_adjusted_recommendation": "WATCH"
}
```

### LLY — PIB PARTIAL → PSP EXIT

Current +2.69%, giveback 0.77, CRITICAL urgency with memory support — escalated to EXIT_PROTECT_SHADOW.

### PG / MRK — HOLD confirmed

Survival ≥ 0.99, giveback ≤ 0.30, urgency LOW — PSP confirms HOLD.

### HSBA.L — WATCH (survival 0)

Peak +9.22% but current PnL ≤ 0; giveback 1.0, no take-profit action.

---

## Global Summary (current run)

| Metric | Value |
|--------|-------|
| Total positions | 12 |
| Avg survival probability | 0.406 |
| Avg giveback risk | 0.737 |
| Urgent (HIGH/CRITICAL) | 5 |
| PSP-adjusted: HOLD / WATCH / EXIT | 4 / 5 / 1 |
| Final verdict | `PSP_SHADOW_READY_FOR_OBSERVATION` |

**Top giveback risk:** HSBA.L, SIE.DE, AAPL, QQQ, MU

---

## Live Execution Confirmation

| Check | Status |
|-------|--------|
| BUY/SELL executed | **NO** |
| `live_trading_impact` | `NONE` |
| `mode` | `SHADOW_ONLY` |
| Broker touched | **NO** |

---

## Overall Verdict

**PASS** — PIB v2 PSP implemented, validated, outputs generated. Live trading unchanged.
