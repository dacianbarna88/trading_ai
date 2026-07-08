# TAE Full PAPER Cycle Report

**Generated:** 2026-07-08T15:51:17+00:00
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
- Confidence: **85.0**

## Promotion gate (live_promotion_allowed=false)

- Counts: `{"PROMOTE_TO_LIVE_CANDIDATE": 0, "CONTINUE_PAPER": 6, "REJECT": 1, "NEEDS_MORE_DATA": 18}`

## Infrastructure & safety

- Infrastructure: **PASS**
- Safety status: **PASS**
- Forbidden content diff clean: **True**
- Forbidden mtime drift detected: **True**
- Forbidden files unchanged (content): **True**

## PAPER execution intelligence

- PAPER portfolio value: **$30,038.13**
- PAPER cash: **$12,321.97**
- PAPER unrealized PnL: **$112.74**
- PAPER realized PnL: **$-415.53**
- PAPER total PnL: **$-302.79**
- PAPER reconciliation: **PASS**
- Canonical vs PAPER value delta: **$-302.78**
- Mark-to-market status: **PARTIAL_STALE**
- Mark-to-market live prices: **5**
- Mark-to-market stale prices: **2**
- Executed trades today: **4**
- Rules strengthened: `['LTB-DPE-PHIL-001', 'LTB-LIFE-LLY-05', 'LTB-CONF-SCORE_PERSISTENCE_AFTER_', 'LTB-CONF-STOP_REENTRY_CHURN', 'LTB-CONF-MISSED_PROFIT_PROTECTION']`
- Rules weakened: `['LTB-PROT-AAPL', 'SCORE_DECAY_SHADOW', 'LTB-LIFE-SPY-04']`
- Top profitable rules: `[{'rule_id': 'LTB-LIFE-PM-03', 'avg_actual_pnl': 94.6425}, {'rule_id': 'LTB-LIFE-LLY-05', 'avg_actual_pnl': 67.24}, {'rule_id': 'LTB-PROT-LLY', 'avg_actual_pnl': 67.24}]`
- Top damaging rules: `[{'rule_id': 'LTB-LIFE-SPY-04', 'avg_actual_pnl': -36.6429}, {'rule_id': 'STOP_REENTRY_CHURN', 'avg_actual_pnl': -32.4935}, {'rule_id': 'LTB-PROT-AAPL', 'avg_actual_pnl': -26.1639}]`
- Top disabled rules: `[]`
- Top deprecated rules: `[]`
- Top trusted rules: `[]`
- Decisions blocked (no PAPER position): **17**
- Losing positions evaluated: `[]`

## Top PAPER actions (by confidence)

- BUY_PAPER: `[]`
- SELL_PAPER: `[{'ticker': 'QQQ', 'confidence': 0.925, 'horizon_reason': '7D=NEGATIVE(-1.4%); 1M=NEGATIVE(-1.5%); 1Y=POSITIVE(28.2%); 2Y=POSITIVE(41.7%); 5Y=POSITIVE(96.4%); 10Y=POSITIVE(538.8%); 20Y=POSITIVE(1786.0%); short-vs-long CONFLICT'}]`
- PROTECT_PAPER: `[{'ticker': 'AAPL', 'confidence': 0.867, 'horizon_reason': '7D=POSITIVE(0.7%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'LLY', 'confidence': 0.856, 'horizon_reason': '7D=POSITIVE(2.7%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'MC.PA', 'confidence': 0.398, 'horizon_reason': '7D=NEGATIVE(-0.6%); 1M=POSITIVE(1.4%); 1Y=POSITIVE(15.8%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- ROTATE_PAPER: `[]`
- HOLD_PAPER: `[{'ticker': 'SPY', 'confidence': 0.673, 'horizon_reason': '7D=POSITIVE(1.8%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=POSITIVE(33.5%); 5Y=POSITIVE(72.1%); 10Y=POSITIVE(248.7%); 20Y=POSITIVE(484.5%); horizons aligned'}, {'ticker': 'PM', 'confidence': 0.615, 'horizon_reason': '7D=NEGATIVE(-0.8%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'PG', 'confidence': 0.614, 'horizon_reason': '7D=POSITIVE(2.9%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}, {'ticker': 'MRK', 'confidence': 0.59, 'horizon_reason': '7D=POSITIVE(1.4%); 1M=NEUTRAL(0.6%); 1Y=POSITIVE(20.9%); 2Y=UNKNOWN(n/a); 5Y=UNKNOWN(n/a); 10Y=UNKNOWN(n/a); 20Y=UNKNOWN(n/a); horizons aligned'}]`
- Note: mtime drift ignored, content diff clean
- Stale sources: none flagged
- Failed steps: none

## Daily operator command

```bash
python3 tae.py full-paper-cycle
```
