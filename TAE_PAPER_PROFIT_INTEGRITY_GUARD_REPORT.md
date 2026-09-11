# TAE PAPER Profit Integrity Guard Report

**Generated:** 2026-09-11T14:01:30+00:00
**Verdict:** **PAPER_PROFIT_INTEGRITY_CLOSED**
**Validation safe to resume:** **True**

## Metrics

- Validation capital base: **$30,000.00**
- Account value: **$29,754.83**
- Profit vs $30k base: **$-245.17**
- Realized PnL: **$-427.00**
- Unrealized PnL: **$-159.09**

## Checks

| check | pass | detail |
| --- | --- | --- |
| no_synthetic_fill_fallback | True | price_for_ticker/fill_price_for_position return 0.0 without mark |
| validation_capital_base_exact | True |  |
| account_value_formula | True | cash + open_positions_value |
| profit_vs_capital_base_formula | True | account_value - validation_capital_base |
| no_synthetic_contamination | True | 0 |
| portfolio_reconciliation | True |  |

## Contamination

- none detected
