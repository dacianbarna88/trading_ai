# TAE Capital Base Integrity Audit

**Status:** **NEEDS_OPERATOR_CONFIRMATION**
**Generated:** 2026-06-29T23:14:45.221854+00:00

## Starting capital

- Config (canonical): **30000.0**
- Sources: {'live_bot.py': 30000.0, 'config/settings.py': 20000.0}

## DEPOSIT / CASH rows

- 2026-06-15 09:01:28 | CASH | $10000.0 | NON_TRADING_VIRTUAL | DEPOSIT | VIRTUAL CAPITAL TEST

## Capital summary

- Deposits detected: 10000.0
- Deposits counted toward capital: 0.0
- Deposits excluded (virtual/unknown): 10000.0
- **Effective contributed capital:** 30000.0

## Cash & account value

- Cash (canonical): 19954.03
- Cash (live_bot style, no DEPOSIT): 19954.03
- Cash (if all deposits counted): 29954.03
- Open positions value: 10441.4351
- Account value (cash + positions): **30395.47**
- Account value (capital + trading PnL): **30395.46**
- Trading PnL (corrected): 395.4641

## Formulas

- `cash_available`: starting_capital_config + capital_deposits_counted - spent + received
- `account_value_cash_based`: cash_available + open_positions_value
- `account_value_capital_based`: effective_contributed_capital + corrected_total_trading_pnl
- `effective_contributed_capital`: starting_capital_config + capital_deposits_counted
- `live_bot_cash`: STARTING_CAPITAL - spent + received (ignores DEPOSIT)

## Explanation

- starting_capital_config=30000.0 (source: live_bot.py)
- cash_available = starting_capital_config + capital_deposits_counted - spent + received
-   spent=50110.0526, received=40064.0817
- account_value_cash_based = cash_available + open_positions_value
- account_value_capital_based = effective_contributed_capital + corrected_total_trading_pnl
- effective_contributed_capital = starting_capital_config + capital_deposits_counted
- Excluded 10000.0 as NON_TRADING_VIRTUAL deposit(s) — not added to effective_contributed_capital (Reason/Signal contains VIRTUAL/TEST markers).
- Prior double-path risk: adding all detected deposits (10000.0) to starting capital raises cash from 19954.03 to 29954.03 while live_bot.py ignores DEPOSIT rows entirely.

## Verdict

- Real capital base for display: **30000.0**
- Prior snapshot double-counted virtual deposit: **True**
- Authoritative account value: **30395.47**
