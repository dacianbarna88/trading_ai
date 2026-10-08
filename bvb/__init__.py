"""Research lab for the Bucharest Stock Exchange (BVB), for Dacian's real
bt-trade.ro account -- requested 2026-10-08: "vreau sa imi analizeze bursa
din romania, ca sa pot tranzactiona pe acest cont luand decizii de buy sau
sell urmand cele 2 sisteme" (analyze the Romanian market so real buy/sell
decisions on that account can follow tae2's and the stocks lab's methods).

Two signals, each a direct port of a system already live elsewhere in this
project -- same mechanism, same honesty standard, NOT retuned for BVB:
- Trend sleeve: tae2's SMA-crossover trend filter (core_gtaa_50's own
  sma_months=6), applied to the LONG-HISTORY BVB names only (data.LONG_HISTORY,
  >=15 years) so the same 15-year gate can be honestly evaluated.
- Momentum ranking: stocks.strategies.momentum() unchanged (12-1 formation,
  absolute-momentum cash filter), applied to the FULL BVB universe
  (data.UNIVERSE), same as momentum_vt10's own construction.

NOT wired to any broker -- Alpaca (tae2's and the stocks lab's paper broker)
does not support BVB at all. This package only ever produces a signal
snapshot (strategies.py + research.py's `signal_today()`) for Dacian to
execute BY HAND on bt-trade.ro. Nothing here places an order.

Known, deliberate differences from tae2/the stocks lab, not oversights:
- CASH is a literal 0%-return column (data.CASH), not a real T-bill ETF like
  tae2's SHY -- no equivalent accessible, documented instrument was found
  for idle RON on this specific account. A conservative simplification: real
  idle cash may earn a little more than 0%, never less.
- cost_bps defaults to tae2.config.COST_BPS (10bps) as a baseline only; this
  almost certainly UNDERSTATES real BT Trade commissions (typically a
  percentage per trade well above US ETF costs). Check the account's own fee
  schedule before trusting net-of-cost turnover, especially for the
  monthly-rebalanced momentum sleeve.
- No 60/40-style bond blend: no accessible RON bond instrument was found
  either, so the trend sleeve is 100% in-or-cash per name, not blended with
  a fixed income core the way core_gtaa_50 is.

See data.py for the exact ticker list, each one's real yfinance history
start, and the liquidity/history tiers.
"""
