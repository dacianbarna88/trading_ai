# TAE Canonical vs PAPER Portfolio Report

**Generated:** 2026-09-03T13:15:21+00:00
**Mode:** PAPER_ONLY — READ_ONLY comparison

| metric | canonical | PAPER | delta |
| --- | --- | --- | --- |
| total value | $30,382.07 | $30,705.22 | $323.15 |
| cash | $229.72 | $94.58 | $-135.14 |
| open positions | 12 | 14 | +2 |
| realized PnL | $0.00 | $102.10 | $102.10 |
| unrealized PnL | $0.00 | $262.20 | $262.20 |
| total PnL | $0.00 | $364.30 | $364.30 |

## PAPER reconciliation

- Status: **PASS**
- total_value: **PASS** expected=30705.221 actual=30705.221
- open_positions_value: **PASS** expected=30610.6363 actual=30610.6362
- unrealized_pnl: **PASS** expected=262.204 actual=262.2039
- total_pnl: **PASS** expected=364.3008 actual=364.3008
- value_delta: **PASS** expected=364.3008 actual=364.301

**Explanation:** PAPER portfolio diverges by $323.15 total value (+2 positions, $-135.14 cash delta, $102.10 realized delta, $262.20 unrealized delta) after isolated PAPER execution and mark-to-market.
