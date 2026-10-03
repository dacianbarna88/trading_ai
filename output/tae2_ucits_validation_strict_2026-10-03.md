# tae2 UCITS twin — validation run, variant=strict, 2026-10-03

core_gtaa_50's EXISTING live parameters (sma_months=6, core_weight=0.5), unchanged, run on UCITS-equivalent price data. See tae2_ucits/data.py for exactly what's real vs spliced in this variant.

Data: 2011-06-01 to 2026-10-01 (15.3 years), split at 2019-02-01.

| Metric | 60/40 (UCITS, benchmark) | core_gtaa_50 (UCITS) |
|---|---:|---:|
| CAGR | 9.6% | 6.6% |
| Vol | 9.3% | 6.5% |
| Sharpe | 1.03 | 1.02 |
| Max drawdown | -20.9% | -13.8% |
| Sharpe, first half | 1.16 | 0.99 |
| Sharpe, second half | 0.97 | 1.05 |
| Out-of-sample Sharpe (after 2019) | — | 1.05 |
| Deflated Sharpe | — | 1.00 |

## Gate details

- ✗ history: 14.5 years (need 15)
- ✓ costs: 10 bps per dollar traded (need 10)
- ✗ beats benchmark, both halves: Sharpe 0.99 vs 1.16, then 1.05 vs 0.97
- ✓ drawdown no worse: -13.8% vs -20.9%
- ✓ deflated Sharpe: 1.00 (need 0.95)

**Verdict: FAIL**

