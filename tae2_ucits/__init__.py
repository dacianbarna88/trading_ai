"""UCITS-accessible research twin of tae2's core_gtaa_50, for a Romanian
(EU) retail investor who can't legally buy US-domiciled ETFs on Alpaca
(PRIIPs -- no KID document). Reuses tae2's strategy/backtest/gates code
completely unchanged; only the input price data differs (real UCITS ETF
listings, verified via yfinance, standing in for each US ticker). See
this package's data.py for exactly which fund and what's approximated.

CHECKPOINT (2026-10-04): RESEARCH_VALIDATED / NOT_LIVE_APPROVED
=================================================================
core_gtaa_50 is UNCHANGED throughout this checkpoint -- same sma_months=6,
core_weight=0.5, same assets, same signals, same gates. Nothing here
retunes the strategy; only the data/benchmarks used to study it changed.

Two data variants, never blurred together (see data.py for the full
provenance table and splice mechanics):

  UCITS STRICT -- real, clean UCITS history only (2011-06-01 onward,
  IBTS.L/IUSP.L's feed is corrupted before that). Gate result: **FAIL**
  (history 14.5y < 15y needed; also fails "beats benchmark both halves" in
  2011-2019). This is not a bug to paper over -- it is the honest result of
  the shortest-available real-data window, and must not be reinterpreted.

  UCITS EXTENDED -- STRICT plus a documented splice recovering 2008-2011:
  for SPY/IEF/VNQ/SHY/EFA, the ORIGINAL US ticker's own real returns before
  2011-06-01 (RECOVERY_SPLICE_DATE in data.py), switching to the real UCITS
  fund from that date on. DBC unaffected (its own US->CMOD.L splice already
  reaches 2006). Gate result: **PASS**, all 5 gates, 2008-01-02 to today
  (17.4y, split 2017-01-01) -- matching tae2's own original EVAL_START/
  SPLIT_DATE as closely as possible.

Why STRICT fails and EXTENDED passes is itself the finding (autopsy.py):
on PURE US DATA restricted to the same short 2011-2019 window, core_gtaa_50
ALSO fails the same gate. The 2011-06-01 floor (forced by a data-quality
problem, not by anything UCITS-specific) cuts out exactly the 2008 crisis
that justifies a trend-following sleeve's existence. Recovering that period
via EXTENDED's documented splice is what restores the pass -- not a UCITS
vs US difference.

Economic conclusion (benchmark_study.py, UCITS EXTENDED, 2008-2026):
TAE2 behaves like INSURANCE: it gives up return in ordinary up markets to
cut losses sharply in major stress episodes.
  - CAGR ~7.0%, volatility ~7.7%, Max Drawdown ~-13.6%
  - Risk-matched by volatility: the 40/60 passive mix (vol 7.5%, CAGR 6.6%
    -- TAE2 still wins on return at the same volatility)
  - Risk-matched by Max Drawdown: the 20/80 passive mix (DD -15.3%, CAGR
    4.7% -- TAE2 wins by +2.3pp at the same drawdown risk)
  - Cost of the insurance: ~3.0%/year given up vs 60/40 in SPY-up years
    (16 of 19); ~6.5%/year gained vs 60/40 in SPY-down years (3 of 19)

Negative/inconclusive results, kept on the record rather than smoothed over:
  - 2015-2016 (China/oil selloff): TAE2 -1.9% vs 60/40 -2.4% -- essentially
    no defensive edge that episode.
  - 2022 bear market: a real whipsaw. The SPY trend signal exited 2022-01-31
    but RE-ENTERED 2022-03-31, mid-bear-market, too early -- TAE2 still
    took -5.4% drawdown that year (vs 60/40's -15.5%: much better, but not
    the clean "exit and stay out" pattern seen in 2008/2011/2018/COVID).

The OFFICIAL 60/40 benchmark and the 5 gates in tae2/config.py are
UNCHANGED by any of this -- the 100/0..20/80 family and the crisis/rolling-
window analysis are informational only, run with tae2.backtest/tae2.gates
completely unmodified.

Full reports: output/tae2_ucits_validation_{strict,extended}_*.md,
output/tae2_benchmark_family_{US_original,UCITS_strict,UCITS_extended}_*.md.
Frontier charts: https://claude.ai/artifact/M1xFW3jWXXMHMqPGeaXCYh

STATUS: RESEARCH_VALIDATED. NOT_LIVE_APPROVED -- no broker wiring, no
capital decision, and the 2022 whipsaw is explicitly left unaddressed (no
parameter change attempted). Any future tuning becomes a separate,
independently-named, independently-validated variant -- never a silent
edit of core_gtaa_50.
"""
