# TAE Canonical vs PAPER Portfolio Report

**Generated:** 2026-09-11T13:37:29+00:00
**Mode:** PAPER_ONLY — READ_ONLY comparison

| metric | canonical | PAPER | delta |
| --- | --- | --- | --- |
| total value | $29,864.54 | $29,754.83 | $-109.71 |
| cash | $4,504.30 | $129.33 | $-4,374.97 |
| open positions | 11 | 28 | +17 |
| realized PnL | $0.00 | $-427.00 | $-427.00 |
| unrealized PnL | $0.00 | $-159.09 | $-159.09 |
| total PnL | $0.00 | $-586.09 | $-586.09 |

## PAPER reconciliation

- Status: **PASS**
- total_value: **PASS** expected=29754.8283 actual=29754.8283
- open_positions_value: **PASS** expected=29625.496 actual=29625.4959
- unrealized_pnl: **PASS** expected=-159.0936 actual=-159.0935
- total_pnl: **PASS** expected=-586.0921 actual=-586.0921
- value_delta: **PASS** expected=-586.0921 actual=-586.0917

**Explanation:** PAPER portfolio diverges by $-109.71 total value (+17 positions, $-4,374.97 cash delta, $-427.00 realized delta, $-159.09 unrealized delta) after isolated PAPER execution and mark-to-market.
