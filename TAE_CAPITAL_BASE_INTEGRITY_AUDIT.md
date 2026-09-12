# TAE Capital Base Integrity Audit

**Status:** **OK**
**Generated:** 2026-09-12T15:00:44.568147+00:00

## Starting capital

- Config (canonical): **30000.0**
- Sources: {'live_bot.py': 30000.0, 'config/settings.py': 30000.0}

## DEPOSIT / CASH rows

- (none)

## Capital summary

- Deposits detected: 0
- Deposits counted toward capital: 0
- Deposits excluded (virtual/unknown): 0
- **Effective contributed capital:** 30000.0

## Cash & account value

- Cash (canonical): 3671.04
- Cash (live_bot style, no DEPOSIT): 3671.04
- Cash (if all deposits counted): 3671.04
- Open positions value: 26199.9772
- Account value (cash + positions): **29871.02**
- Account value (capital + trading PnL): **29871.02**
- Trading PnL (corrected): -128.9796

## Formulas

- `cash_available`: starting_capital_config + capital_deposits_counted - spent + received
- `account_value_cash_based`: cash_available + open_positions_value
- `account_value_capital_based`: effective_contributed_capital + corrected_total_trading_pnl
- `effective_contributed_capital`: starting_capital_config + capital_deposits_counted
- `live_bot_cash`: STARTING_CAPITAL - spent + received (ignores DEPOSIT)

## Explanation

- starting_capital_config=30000.0 (source: live_bot.py)
- cash_available = starting_capital_config + capital_deposits_counted - spent + received
-   spent=171411.1133, received=145082.1565
- account_value_cash_based = cash_available + open_positions_value
- account_value_capital_based = effective_contributed_capital + corrected_total_trading_pnl
- effective_contributed_capital = starting_capital_config + capital_deposits_counted
- cash + open_positions_value closes with effective_contributed_capital + trading_pnl.

## Verdict

- Real capital base for display: **30000.0**
- Prior snapshot double-counted virtual deposit: **False**
- Authoritative account value: **29871.02**
