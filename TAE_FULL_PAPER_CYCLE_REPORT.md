# TAE Full PAPER Cycle Report

**Generated:** 2026-07-08T19:29:59+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE
**Final verdict:** **READY_FOR_PAPER_DAY**

## Portfolio snapshot (read-only accounting)

- Portfolio value: **$30,340.91**
- Cash: **$2,335.28**
- Open positions: **12**
- Total PnL: **$0.00**

## PAPER decision highlights

- PROMISING: **0**
- CONTINUE: **6**
- REJECT: **1**
- NEEDS_MORE_DATA: **18**
- Horizon conflicts: **1**
- Historical runtime all fresh: **True**
- Historical confidence penalty: **0.0**

## DPE & adaptive

- DPE winner: **None**
- Adaptive philosophy: **COLLABORATIVE**
- Confidence: **88.0**

## Promotion gate (live_promotion_allowed=false)

- Counts: `{"PROMOTE_TO_LIVE_CANDIDATE": 0, "CONTINUE_PAPER": 6, "REJECT": 1, "NEEDS_MORE_DATA": 18}`

## Infrastructure & safety

- Infrastructure: **PASS**
- Safety status: **PASS**
- Forbidden content diff clean: **True**
- Forbidden mtime drift detected: **False**
- Forbidden files unchanged (content): **True**

## PAPER execution intelligence

- PAPER portfolio value: **$43,316.37**
- PAPER cash: **$13,739.71**
- PAPER unrealized PnL: **$7,956.37**
- PAPER realized PnL: **$5,019.08**
- PAPER total PnL: **$12,975.45**
- PAPER reconciliation: **PASS**
- Canonical vs PAPER value delta: **$12,975.46**
- Mark-to-market status: **LIVE**
- Mark-to-market live prices: **12**
- Mark-to-market stale prices: **0**
- Executed trades today: **19**
- Rules strengthened: `['LTB-DPE-PHIL-001', 'LTB-STALE-001', 'LTB-CONF-SCORE_PERSISTENCE_AFTER_', 'LTB-CONF-STOP_REENTRY_CHURN', 'LTB-CONF-MISSED_PROFIT_PROTECTION']`
- Rules weakened: `['LTB-OPP-AMAT-03', 'LTB-PROT-AMAT', 'SCORE_DECAY_SHADOW', 'LTB-LIFE-SPY-04']`
- Top profitable rules: `[{'rule_id': 'LTB-PROT-HD', 'avg_actual_pnl': 1710.9916}, {'rule_id': 'LTB-STALE-001', 'avg_actual_pnl': 1568.3228}, {'rule_id': 'SCORE_DECAY_SHADOW', 'avg_actual_pnl': 1038.6171}]`
- Top damaging rules: `[{'rule_id': 'LTB-OPP-AMAT-03', 'avg_actual_pnl': -31.0377}, {'rule_id': 'LTB-PROT-AMAT', 'avg_actual_pnl': -31.0377}, {'rule_id': 'LTB-LIFE-SPY-04', 'avg_actual_pnl': -19.9769}]`
- Top disabled rules: `[]`
- Top deprecated rules: `[]`
- Top trusted rules: `['LTB-CONF-MISSED_PROFIT_PROTECTION', 'LTB-CONF-SCORE_PERSISTENCE_AFTER_', 'LTB-CONF-STOP_REENTRY_CHURN', 'LTB-DPE-PHIL-001', 'LTB-REPLAY-04']`
- Decisions blocked (no PAPER position): **18**
- Losing positions evaluated: `[]`

## Decision state (anti-churn)

- PDE switch authorized: **8**
- PDE switch blocked: **0**
- Execution skipped (unauthorized switch): **0**

## Top PAPER actions (by confidence)

- BUY_PAPER: `[{'ticker': 'AMAT', 'confidence': 0.339, 'horizon_reason': '7D=POSITIVE(4.0%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'AIR.PA', 'confidence': 0.31, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=POSITIVE(1.4%); 1Y=POSITIVE(15.8%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'DIA', 'confidence': 0.31, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=POSITIVE(2.6%); 1Y=POSITIVE(19.5%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'GE', 'confidence': 0.31, 'horizon_reason': '7D=NEUTRAL(0.0%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'HD', 'confidence': 0.25, 'horizon_reason': '7D=NEGATIVE(-1.5%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- SELL_PAPER: `[]`
- PROTECT_PAPER: `[{'ticker': 'AAPL', 'confidence': 0.874, 'horizon_reason': '7D=POSITIVE(0.7%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'LLY', 'confidence': 0.863, 'horizon_reason': '7D=POSITIVE(2.7%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- ROTATE_PAPER: `[]`
- HOLD_PAPER: `[{'ticker': 'MRK', 'confidence': 0.796, 'horizon_reason': '7D=POSITIVE(1.4%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'SPY', 'confidence': 0.682, 'horizon_reason': '7D=POSITIVE(1.8%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=POSITIVE(33.5%); 5Y=POSITIVE(72.1%); 10Y=POSITIVE(248.7%); 20Y=POSITIVE(484.5%); horizons aligned'}, {'ticker': 'PM', 'confidence': 0.624, 'horizon_reason': '7D=NEGATIVE(-0.8%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'PG', 'confidence': 0.623, 'horizon_reason': '7D=POSITIVE(2.9%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'MC.PA', 'confidence': 0.545, 'horizon_reason': '7D=NEGATIVE(-0.6%); 1M=POSITIVE(1.4%); 1Y=POSITIVE(15.8%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- Stale sources: none flagged
- Failed steps: none

## Daily operator command

```bash
python3 tae.py full-paper-cycle
```
