# TAE Full PAPER Cycle Report

**Generated:** 2026-09-03T13:15:23+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE
**Final verdict:** **READY_FOR_PAPER_DAY**

## Portfolio snapshot (read-only accounting)

- Portfolio value: **$30,382.07**
- Cash: **$229.72**
- Open positions: **12**
- Total PnL: **$0.00**

## PAPER decision highlights

- PROMISING: **34**
- CONTINUE: **7**
- REJECT: **0**
- NEEDS_MORE_DATA: **57**
- Horizon conflicts: **1**
- Historical runtime all fresh: **True**
- Historical confidence penalty: **0.0**

## DPE & adaptive

- DPE winner: **COMPETITIVE**
- Adaptive philosophy: **COMPETITIVE**
- Confidence: **72.1**

## Promotion gate (live_promotion_allowed=false)

- Counts: `{"PROMOTE_TO_LIVE_CANDIDATE": 34, "CONTINUE_PAPER": 7, "REJECT": 0, "NEEDS_MORE_DATA": 57}`

## Infrastructure & safety

- Infrastructure: **UNKNOWN**
- Safety status: **PASS**
- Forbidden content diff clean: **True**
- Forbidden mtime drift detected: **True**
- Forbidden files unchanged (content): **True**

## PAPER execution intelligence

- PAPER portfolio value: **$30,705.22**
- PAPER cash: **$94.58**
- PAPER unrealized PnL: **$262.20**
- PAPER realized PnL: **$102.10**
- PAPER total PnL: **$364.30**
- PAPER reconciliation: **PASS**
- Canonical vs PAPER value delta: **$323.15**
- Mark-to-market status: **LIVE**
- Mark-to-market live prices: **14**
- Mark-to-market stale prices: **0**
- Executed trades today: **0**
- Rules strengthened: `['LTB-DPE-PHIL-001', 'LTB-STALE-001', 'LTB-PATTERN-001', 'TAE_SHADOW_SIZING_COMPARISON_V1', 'DO_NOT_PROMOTE_TO_LIVE']`
- Rules weakened: `['LTB-LIFE-LLY-05', 'LTB-LIFE-LLY-04', 'LTB-LIFE-PM-05']`
- Top profitable rules: `[{'rule_id': 'LTB-LIFE-PG-02', 'avg_actual_pnl': 107.142}, {'rule_id': 'LTB-PROT-ALV.DE', 'avg_actual_pnl': 37.4773}, {'rule_id': 'LTB-PROT-ULVR.L', 'avg_actual_pnl': 34.5888}]`
- Top damaging rules: `[{'rule_id': 'LTB-LIFE-PM-05', 'avg_actual_pnl': -98.3474}, {'rule_id': 'LTB-LIFE-LLY-05', 'avg_actual_pnl': -27.104}, {'rule_id': 'LTB-LIFE-LLY-04', 'avg_actual_pnl': -27.104}]`
- Top disabled rules: `['LTB-LIFE-LLY-04', 'LTB-LIFE-PM-05']`
- Top deprecated rules: `[]`
- Top trusted rules: `['LTB-LIFE-PG-02']`
- Decisions blocked (no PAPER position): **84**
- Losing positions evaluated: `[]`

## Decision state (anti-churn)

- PDE switch authorized: **52**
- PDE switch blocked: **0**
- Execution skipped (unauthorized switch): **33**

## Top PAPER actions (by confidence)

- BUY_PAPER: `[{'ticker': 'PM', 'confidence': 0.946, 'horizon_reason': '7D=POSITIVE(2.7%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'LLY', 'confidence': 0.727, 'horizon_reason': '7D=POSITIVE(2.7%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'ADBE', 'confidence': 0.717, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'HPQ', 'confidence': 0.717, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'ICE', 'confidence': 0.717, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- SELL_PAPER: `[]`
- PROTECT_PAPER: `[{'ticker': 'QQQ', 'confidence': 0.652, 'horizon_reason': '7D=NEGATIVE(-1.0%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=POSITIVE(49.7%); 5Y=POSITIVE(88.7%); 10Y=POSITIVE(493.9%); 20Y=POSITIVE(1785.9%); short-vs-long CONFLICT'}]`
- ROTATE_PAPER: `[]`
- HOLD_PAPER: `[{'ticker': 'SPY', 'confidence': 0.939, 'horizon_reason': '7D=POSITIVE(1.4%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=POSITIVE(37.5%); 5Y=POSITIVE(70.7%); 10Y=POSITIVE(244.3%); 20Y=POSITIVE(487.1%); horizons aligned'}, {'ticker': 'MRK', 'confidence': 0.817, 'horizon_reason': '7D=POSITIVE(1.4%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'PG', 'confidence': 0.817, 'horizon_reason': '7D=POSITIVE(2.0%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'DIA', 'confidence': 0.678, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'ALV.DE', 'confidence': 0.662, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEUTRAL(0.0%); 1Y=NEUTRAL(0.0%); 2Y=POSITIVE(65.8%); 5Y=POSITIVE(123.3%); 10Y=POSITIVE(237.6%); 20Y=POSITIVE(251.7%); horizons aligned'}]`
- Note: mtime drift ignored, content diff clean
- Stale sources: none flagged
- Failed steps: none

## Daily operator command

```bash
python3 tae.py full-paper-cycle
```
