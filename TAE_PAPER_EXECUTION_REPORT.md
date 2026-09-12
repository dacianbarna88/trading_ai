# TAE PAPER Execution Report

**Generated:** 2026-09-12T15:01:41+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION

## Run summary

- Decisions consumed: **98**
- Orders created (this run): **98**
- Orders executed (this run): **0**
- Orders skipped (this run): **0**
- Skipped same action: **80**
- Skipped unauthorized switch: **0**
- Accepted action switches: **0**
- Re-executed on action change: **0**
- Trades written (this run): **0**
- Trades file total lines: **544**

## Portfolio delta (this run)

- Positions before: **27**
- Positions after: **27**
- Cash before: **$196.27**
- Cash after: **$196.27**
- Total value: **$30,040.47**

## PnL accounting

- Realized PnL: **$-403.34**
- Unrealized PnL: **$102.89**
- Total PnL: **$-300.45**
- Value delta vs starting: **$-300.45**

## Reconciliation

- Status: **PASS**
- Formula: `total_value = cash + open_positions_value`
- Formula: `total_pnl = realized_pnl + unrealized_pnl`
- Formula: `value_delta = total_value - starting_value`
- total_value: **PASS** expected=30040.4687 actual=30040.4687
- open_positions_value: **PASS** expected=29844.1959 actual=29844.1957
- unrealized_pnl: **PASS** expected=102.8894 actual=102.8893
- total_pnl: **PASS** expected=-300.4517 actual=-300.4517
- value_delta: **PASS** expected=-300.4517 actual=-300.4513

## Validation

- Validation OK: **True**
- No validation errors

## Action summary (this run)

- BUY_PAPER: **18**

## Safety

- broker_executed: **false**
- live_money: **false**
- live_bot.py / portfolio.csv: **untouched**

## Outputs

- `runtime_outputs/paper_execution/paper_portfolio.json`
- `runtime_outputs/paper_execution/paper_orders.jsonl`
- `runtime_outputs/paper_execution/paper_trades.jsonl`
- `runtime_outputs/paper_execution/rule_outcome_attribution.json`
