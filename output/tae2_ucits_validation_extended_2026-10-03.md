# tae2 UCITS twin — validation run, variant=extended, 2026-10-03

core_gtaa_50's EXISTING live parameters (sma_months=6, core_weight=0.5), unchanged, run on UCITS-equivalent price data. See tae2_ucits/data.py for exactly what's real vs spliced in this variant.

Data: 2008-01-02 to 2026-10-01 (18.7 years), split at 2017-01-01.

| Metric | 60/40 (UCITS, benchmark) | core_gtaa_50 (UCITS) |
|---|---:|---:|
| CAGR | 8.4% | 7.0% |
| Vol | 10.7% | 7.7% |
| Sharpe | 0.81 | 0.92 |
| Max drawdown | -31.4% | -13.6% |
| Sharpe, first half | 0.65 | 0.82 |
| Sharpe, second half | 0.98 | 1.05 |
| Out-of-sample Sharpe (after 2017) | — | 1.05 |
| Deflated Sharpe | — | 1.00 |

## Gate details

- ✓ history: 17.4 years (need 15)
- ✓ costs: 10 bps per dollar traded (need 10)
- ✓ beats benchmark, both halves: Sharpe 0.82 vs 0.65, then 1.05 vs 0.98
- ✓ drawdown no worse: -13.6% vs -31.4%
- ✓ deflated Sharpe: 1.00 (need 0.95)

**Verdict: PASS**

