# TAE Next Dollar

**Generated:** 2026-07-15  
**Companion:** `tae_next_dollar.json` (auto-synced each cycle) · Queue SSOT: `tae_roi_queue.json`  
**Work rule:** Only the single **active** ROI. Everything else waits.  
**Orchestration verdict:** `ECONOMIC_ORCHESTRATION_CLOSED`

---

## Verdict

```
NEXT_DOLLAR_IDENTIFIED
```

---

## ROI #1 — work this, nothing else

| Field | Value |
|-------|-------|
| **ROI_ID** | `ROI-001` |
| **ROI_SCORE** | **2.5377** |
| **Subsystem** | Profit Target Adapter → REDUCE_PAPER trim sizing |
| **Estimated upside** | **$29.53** (lock ~$5.93 UPNL + 10% haircut of HSBA missed $235.96) |
| **Capital freed (efficiency, not scored as profit)** | ~$617 HSBA notional (50% PTA vs 20% executed) |
| **Confidence** | MED |
| **Status** | **ECONOMICALLY_POSITIVE** (auto-verdict) |
| **Sample size** | **4 / 10** (auto-refreshed each cycle) |
| **Production flag** | **false** — baseline 20/30% trim until `PROMOTED_PAPER` |
| **Replay available** | YES |
| **Capital required** | $0 |
| **Risk impact** | Lowers DD exposure on COLLAPSED HSBA (`cap_eff=0`) |
| **Hard Risk** | YES compatible |
| **Decision State** | YES compatible |
| **Profit Integrity** | YES compatible |
| **Complexity** | **2 / 10** |
| **Expected replay** | 15–30 min |
| **Promotion readiness** | **CHALLENGER_ONLY** — do not promote |
| **Prior verified PnL on path** | +$3.95 (HSBA REDUCE @ 20%) |

### Evidence

1. `tae_profit_target_adapter.json` — HSBA `suggested_partial_size_pct=50`, urgency CRITICAL, `REDUCE_EXPOSURE_SHADOW`
2. `paper_orders.jsonl` — HSBA REDUCE trimmed **20%**, realized **+$3.95**
3. `tae_paper_execution.py` — `trim_pct = 30 if confidence < 0.7 else 20` — **ignores PTA size**

### Challenger spec (reuse only)

**Module:** `tae_paper_execution.py` · REDUCE_PAPER sizing  

**Behavior:** If held ticker PTA row has urgency ∈ {CRITICAL, HIGH} **or** strategy ∈ {REDUCE_EXPOSURE_SHADOW, TIGHTEN_TRAIL_SHADOW, PROTECT_PROFIT_SHADOW}:

```
trim_pct = clamp(suggested_partial_size_pct, 15, 50)
```

Else keep existing 20/30 heuristic.

**Frozen:** architecture · Hard Risk · Decision State · Profit Integrity · no new engines.

### Success (any one, no regressions)

- Higher realized profit  
- **or** lower drawdown  
- **or** higher profit factor  
- **or** higher expectancy  

No regression: Hard Risk · Decision State · Profit Integrity · Reconciliation.

### After this sprint

Recalculate `tae_roi_queue.json`. A different ROI_ID may become #1.

---

## Queue head (waiting)

| Rank | ID | Score | Upside | Readiness |
|:----:|----|------:|-------:|-----------|
| 1 | ROI-001 | 2.5377 | $29.53 | ← **ACTIVE** |
| 2 | ROI-002 | 1.0158 | $17.73 | waits (depends on 001) |
| 3 | ROI-009 | 0.5376 | $3.91 | waits |
| 4 | ROI-007 | 0.4760 | $27.20 | waits (NOT_READY) |
| 5 | ROI-006 | 0.3996 | $19.03 | waits |
