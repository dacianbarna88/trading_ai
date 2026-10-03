"""UCITS-accessible research twin of tae2's core_gtaa_50, for a Romanian
(EU) retail investor who can't legally buy US-domiciled ETFs on Alpaca
(PRIIPs -- no KID document). Reuses tae2's strategy/backtest/gates code
completely unchanged; only the input price data differs (real UCITS ETF
listings, verified via yfinance, standing in for each US ticker). See
this package's data.py for exactly which fund and what's approximated.
"""
