# TAE PAPER Execution Report

**Generated:** 2026-09-03T13:02:15+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION

## Run summary

- Decisions consumed: **98**
- Orders created (this run): **98**
- Orders executed (this run): **0**
- Orders skipped (this run): **1**
- Skipped same action: **59**
- Skipped unauthorized switch: **1**
- Accepted action switches: **0**
- Re-executed on action change: **0**
- Trades written (this run): **0**
- Trades file total lines: **275**

## Portfolio delta (this run)

- Positions before: **14**
- Positions after: **14**
- Cash before: **$94.58**
- Cash after: **$94.58**
- Total value: **$30,721.53**

## PnL accounting

- Realized PnL: **$102.10**
- Unrealized PnL: **$278.51**
- Total PnL: **$380.61**
- Value delta vs starting: **$380.61**

## Reconciliation

- Status: **PASS**
- Formula: `total_value = cash + open_positions_value`
- Formula: `total_pnl = realized_pnl + unrealized_pnl`
- Formula: `value_delta = total_value - starting_value`
- total_value: **PASS** expected=30721.5303 actual=30721.5303
- open_positions_value: **PASS** expected=30626.9456 actual=30626.9455
- unrealized_pnl: **PASS** expected=278.5133 actual=278.5132
- total_pnl: **PASS** expected=380.6101 actual=380.6101
- value_delta: **PASS** expected=380.6101 actual=380.6103

## Validation

- Validation OK: **True**
- No validation errors

## Action summary (this run)

- BUY_PAPER: **38**

## Safety

- broker_executed: **false**
- live_money: **false**
- live_bot.py / portfolio.csv: **untouched**

## Outputs

- `runtime_outputs/paper_execution/paper_portfolio.json`
- `runtime_outputs/paper_execution/paper_orders.jsonl`
- `runtime_outputs/paper_execution/paper_trades.jsonl`
- `runtime_outputs/paper_execution/rule_outcome_attribution.json`
