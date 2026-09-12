# TAE Full PAPER Cycle Report

**Generated:** 2026-09-12T15:23:20+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE
**Final verdict:** **READY_FOR_PAPER_DAY**

## Portfolio snapshot (read-only accounting)

- Portfolio value: **$29,871.02**
- Cash: **$3,671.04**
- Open positions: **11**
- Total PnL: **$0.00**

## PAPER decision highlights

- PROMISING: **15**
- CONTINUE: **9**
- REJECT: **0**
- NEEDS_MORE_DATA: **74**
- Horizon conflicts: **0**
- Historical runtime all fresh: **True**
- Historical confidence penalty: **0.0**

## DPE & adaptive

- DPE winner: **TIE**
- Adaptive philosophy: **COMPETITIVE**
- Confidence: **66.9**

## Promotion gate (live_promotion_allowed=false)

- Counts: `{"PROMOTE_TO_LIVE_CANDIDATE": 15, "CONTINUE_PAPER": 9, "REJECT": 0, "NEEDS_MORE_DATA": 74}`

## Infrastructure & safety

- Infrastructure: **UNKNOWN**
- Safety status: **PASS**
- Forbidden content diff clean: **True**
- Forbidden mtime drift detected: **False**
- Forbidden files unchanged (content): **True**

## PAPER execution intelligence

- PAPER portfolio value: **$30,040.47**
- PAPER cash: **$196.27**
- PAPER unrealized PnL: **$102.89**
- PAPER realized PnL: **$-403.34**
- PAPER total PnL: **$-300.45**
- PAPER reconciliation: **PASS**
- Canonical vs PAPER value delta: **$169.45**
- Mark-to-market status: **LIVE**
- Mark-to-market live prices: **27**
- Mark-to-market stale prices: **0**
- Executed trades today: **2**
- Rules strengthened: `['TAE_SHADOW_SIZING_COMPARISON_V1', 'LTB-OPP-HSBA.L-01', 'LTB-PROT-ALV.DE', 'LTB-LIFE-PM-05', 'LTB-PROT-PPG-HSBA.L']`
- Rules weakened: `['LTB-DPE-PHIL-001', 'LTB-STALE-001', 'LTB-PATTERN-001', 'DO_NOT_PROMOTE_TO_LIVE', 'KNOW-HOLD_PAPER']`
- Top profitable rules: `[{'rule_id': 'LTB-PROT-ALV.DE', 'avg_actual_pnl': 12.5248}, {'rule_id': 'LTB-LIFE-PG-02', 'avg_actual_pnl': 12.3511}, {'rule_id': 'LTB-LIFE-PM-05', 'avg_actual_pnl': 11.558}]`
- Top damaging rules: `[{'rule_id': 'LTB-LIFE-MRK-01', 'avg_actual_pnl': -85.0824}, {'rule_id': 'LTB-PROT-ULVR.L', 'avg_actual_pnl': -20.464}, {'rule_id': 'LTB-PROT-PPG-ULVR.L', 'avg_actual_pnl': -20.464}]`
- Top disabled rules: `['LTB-LIFE-MRK-01']`
- Top deprecated rules: `['LTB-LIFE-LLY-04']`
- Top trusted rules: `['LTB-LIFE-PG-02', 'LTB-LIFE-PM-05']`
- Decisions blocked (no PAPER position): **71**
- Losing positions evaluated: `[]`

## Decision state (anti-churn)

- PDE switch authorized: **68**
- PDE switch blocked: **6**
- Execution skipped (unauthorized switch): **91**

## Top PAPER actions (by confidence)

- BUY_PAPER: `[{'ticker': 'CRWD', 'confidence': 0.773, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'JPM', 'confidence': 0.773, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'ALV.DE', 'confidence': 0.472, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-2.4%); 1Y=POSITIVE(16.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'NVDA', 'confidence': 0.465, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'ADI', 'confidence': 0.355, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- SELL_PAPER: `[{'ticker': 'ANET', 'confidence': 0.95, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'HSBA.L', 'confidence': 0.95, 'horizon_reason': '7D=NEUTRAL(-0.2%); 1M=NEUTRAL(-0.9%); 1Y=POSITIVE(18.2%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'BP.L', 'confidence': 0.794, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEUTRAL(-0.9%); 1Y=POSITIVE(18.2%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'AMD', 'confidence': 0.656, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- PROTECT_PAPER: `[{'ticker': 'QQQ', 'confidence': 0.568, 'horizon_reason': '7D=NEGATIVE(-1.0%); 1M=NEGATIVE(-1.2%); 1Y=POSITIVE(22.4%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- ROTATE_PAPER: `[]`
- HOLD_PAPER: `[{'ticker': 'DELL', 'confidence': 0.95, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'HPQ', 'confidence': 0.95, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'PG', 'confidence': 0.95, 'horizon_reason': '7D=POSITIVE(2.0%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'PM', 'confidence': 0.95, 'horizon_reason': '7D=POSITIVE(2.7%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'LLY', 'confidence': 0.918, 'horizon_reason': '7D=POSITIVE(2.7%); 1M=NEGATIVE(-1.1%); 1Y=POSITIVE(17.6%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- Stale sources: none flagged
- Failed steps: none

## Daily operator command

```bash
python3 tae.py full-paper-cycle
```
