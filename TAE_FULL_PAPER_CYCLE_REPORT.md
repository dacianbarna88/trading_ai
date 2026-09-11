# TAE Full PAPER Cycle Report

**Generated:** 2026-09-11T13:14:47+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE
**Final verdict:** **BLOCKED_WITH_REASONS**

## Portfolio snapshot (read-only accounting)

- Portfolio value: **$29,864.54**
- Cash: **$4,504.30**
- Open positions: **11**
- Total PnL: **$0.00**

## PAPER decision highlights

- PROMISING: **14**
- CONTINUE: **12**
- REJECT: **0**
- NEEDS_MORE_DATA: **72**
- Horizon conflicts: **0**
- Historical runtime all fresh: **True**
- Historical confidence penalty: **0.0**

## DPE & adaptive

- DPE winner: **TIE**
- Adaptive philosophy: **COMPETITIVE**
- Confidence: **67.2**

## Promotion gate (live_promotion_allowed=false)

- Counts: `{"PROMOTE_TO_LIVE_CANDIDATE": 14, "CONTINUE_PAPER": 12, "REJECT": 0, "NEEDS_MORE_DATA": 72}`

## Infrastructure & safety

- Infrastructure: **UNKNOWN**
- Safety status: **BLOCKED**
- Forbidden content diff clean: **False**
- Forbidden mtime drift detected: **False**
- Forbidden files unchanged (content): **False**

## PAPER execution intelligence

- PAPER portfolio value: **$29,754.83**
- PAPER cash: **$129.33**
- PAPER unrealized PnL: **$-159.09**
- PAPER realized PnL: **$-427.00**
- PAPER total PnL: **$-586.09**
- PAPER reconciliation: **PASS**
- Canonical vs PAPER value delta: **$-109.71**
- Mark-to-market status: **LIVE**
- Mark-to-market live prices: **28**
- Mark-to-market stale prices: **0**
- Executed trades today: **33**
- Rules strengthened: `['LTB-OPP-HSBA.L-01', 'LTB-PROT-ALV.DE', 'LTB-LIFE-PM-05', 'LTB-PROT-PPG-HSBA.L']`
- Rules weakened: `['LTB-DPE-PHIL-001', 'LTB-STALE-001', 'LTB-LOSS-LOSS-CRYSTALLIZATION-ABF990', 'LTB-PATTERN-001', 'DO_NOT_PROMOTE_TO_LIVE']`
- Top profitable rules: `[{'rule_id': 'LTB-PROT-ALV.DE', 'avg_actual_pnl': 17.8996}, {'rule_id': 'LTB-LIFE-PM-05', 'avg_actual_pnl': 9.7912}, {'rule_id': 'LTB-OPP-HSBA.L-01', 'avg_actual_pnl': 4.3587}]`
- Top damaging rules: `[{'rule_id': 'LTB-LIFE-PG-02', 'avg_actual_pnl': -79.6404}, {'rule_id': 'LTB-LIFE-MRK-01', 'avg_actual_pnl': -64.3947}, {'rule_id': 'LTB-PROT-ULVR.L', 'avg_actual_pnl': -12.8217}]`
- Top disabled rules: `['LTB-LIFE-MRK-01', 'LTB-LIFE-PG-02']`
- Top deprecated rules: `['DO_NOT_PROMOTE_TO_LIVE', 'KNOW-BUY_PAPER', 'KNOW-HOLD_PAPER', 'KNOW-SELL_PAPER', 'LTB-DPE-PHIL-001']`
- Top trusted rules: `['LTB-LIFE-PM-05']`
- Decisions blocked (no PAPER position): **70**
- Losing positions evaluated: `[]`

## Decision state (anti-churn)

- PDE switch authorized: **74**
- PDE switch blocked: **0**
- Execution skipped (unauthorized switch): **80**

## Top PAPER actions (by confidence)

- BUY_PAPER: `[{'ticker': 'MRK', 'confidence': 0.83, 'horizon_reason': '7D=POSITIVE(1.4%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'CRWD', 'confidence': 0.67, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'AAPL', 'confidence': 0.54, 'horizon_reason': '7D=NEUTRAL(-0.1%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'ABBV', 'confidence': 0.54, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'NVDA', 'confidence': 0.426, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- SELL_PAPER: `[{'ticker': 'HSBA.L', 'confidence': 0.95, 'horizon_reason': '7D=NEUTRAL(-0.2%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'BP.L', 'confidence': 0.807, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'AMD', 'confidence': 0.67, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'ANET', 'confidence': 0.67, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'CME', 'confidence': 0.67, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- PROTECT_PAPER: `[{'ticker': 'QQQ', 'confidence': 0.484, 'horizon_reason': '7D=NEGATIVE(-1.0%); 1M=NEGATIVE(-1.4%); 1Y=POSITIVE(21.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- ROTATE_PAPER: `[]`
- HOLD_PAPER: `[{'ticker': 'PG', 'confidence': 0.95, 'horizon_reason': '7D=POSITIVE(2.0%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'PM', 'confidence': 0.95, 'horizon_reason': '7D=POSITIVE(2.7%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'LLY', 'confidence': 0.918, 'horizon_reason': '7D=POSITIVE(2.7%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'SPY', 'confidence': 0.845, 'horizon_reason': '7D=POSITIVE(1.4%); 1M=NEGATIVE(-1.6%); 1Y=POSITIVE(16.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'DIA', 'confidence': 0.653, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEGATIVE(-3.0%); 1Y=POSITIVE(14.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- Safety block reason: **forbidden content diff: core/market_data_layer.py**
- Changed files: `['core/market_data_layer.py']`
- Stale sources: none flagged
- Failed steps: none

## Daily operator command

```bash
python3 tae.py full-paper-cycle
```
