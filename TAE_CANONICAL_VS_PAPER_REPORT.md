# TAE Canonical vs PAPER Portfolio Report

**Generated:** 2026-09-12T15:23:16+00:00
**Mode:** PAPER_ONLY — READ_ONLY comparison

| metric | canonical | PAPER | delta |
| --- | --- | --- | --- |
| total value | $29,871.02 | $30,040.47 | $169.45 |
| cash | $3,671.04 | $196.27 | $-3,474.77 |
| open positions | 11 | 27 | +16 |
| realized PnL | $0.00 | $-403.34 | $-403.34 |
| unrealized PnL | $0.00 | $102.89 | $102.89 |
| total PnL | $0.00 | $-300.45 | $-300.45 |

## PAPER reconciliation

- Status: **PASS**
- total_value: **PASS** expected=30040.4687 actual=30040.4687
- open_positions_value: **PASS** expected=29844.1959 actual=29844.1957
- unrealized_pnl: **PASS** expected=102.8894 actual=102.8893
- total_pnl: **PASS** expected=-300.4517 actual=-300.4517
- value_delta: **PASS** expected=-300.4517 actual=-300.4513

**Explanation:** PAPER portfolio diverges by $169.45 total value (+16 positions, $-3,474.77 cash delta, $-403.34 realized delta, $102.89 unrealized delta) after isolated PAPER execution and mark-to-market.
