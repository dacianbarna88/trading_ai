# TAE PAPER Execution Report

**Generated:** 2026-09-11T14:01:30+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION

## Run summary

- Decisions consumed: **98**
- Orders created (this run): **98**
- Orders executed (this run): **0**
- Orders skipped (this run): **0**
- Skipped same action: **80**
- Skipped unauthorized switch: **0**
- Accepted action switches: **2**
- Re-executed on action change: **2**
- Trades written (this run): **0**
- Trades file total lines: **536**

## Portfolio delta (this run)

- Positions before: **28**
- Positions after: **28**
- Cash before: **$129.33**
- Cash after: **$129.33**
- Total value: **$29,754.83**

## PnL accounting

- Realized PnL: **$-427.00**
- Unrealized PnL: **$-159.09**
- Total PnL: **$-586.09**
- Value delta vs starting: **$-586.09**

## Reconciliation

- Status: **PASS**
- Formula: `total_value = cash + open_positions_value`
- Formula: `total_pnl = realized_pnl + unrealized_pnl`
- Formula: `value_delta = total_value - starting_value`
- total_value: **PASS** expected=29754.8283 actual=29754.8283
- open_positions_value: **PASS** expected=29625.496 actual=29625.4959
- unrealized_pnl: **PASS** expected=-159.0936 actual=-159.0935
- total_pnl: **PASS** expected=-586.0921 actual=-586.0921
- value_delta: **PASS** expected=-586.0921 actual=-586.0917

## Validation

- Validation OK: **True**
- No validation errors

## Action summary (this run)

- BUY_PAPER: **16**
- HOLD_PAPER: **1**
- SKIP_PAPER: **1**

## Safety

- broker_executed: **false**
- live_money: **false**
- live_bot.py / portfolio.csv: **untouched**

## Outputs

- `runtime_outputs/paper_execution/paper_portfolio.json`
- `runtime_outputs/paper_execution/paper_orders.jsonl`
- `runtime_outputs/paper_execution/paper_trades.jsonl`
- `runtime_outputs/paper_execution/rule_outcome_attribution.json`
