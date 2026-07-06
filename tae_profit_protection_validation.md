# TAE Profit Protection Historical Validation (X.PROTECT-2)

**Generated:** 2026-07-06T13:26:41
**Mode:** SHADOW_ONLY | **Verdict:** PROMISING_BUT_NOT_READY

## Dataset health
- Observations: **108**
- Unique days: 5 | Tickers: 14
- Date range: ['2026-06-30', '2026-07-06']
- Data quality: GOOD
- Confidence: **HIGH**
- Minimum sample warning: False

## Strategy ranking

| Strategy | Total | Δ vs HOLD | Win rate | Cut winners rate |
|----------|-------|-----------|----------|------------------|
| shadow_trailing_1 | 5601.18 | 3642.76 | 44% | 1% |
| shadow_trailing_1_5 | 5107.29 | 3148.87 | 41% | 1% |
| shadow_sell_30 | 3626.52 | 1668.1 | 100% | 0% |
| shadow_sell_20 | 3085.63 | 1127.21 | 100% | 0% |
| HOLD | 1958.42 | 0.0 | 0% | 0% |

## Best strategy
- **shadow_trailing_1** — total 5601.18 USD
- HOLD baseline: 1958.42 USD
- Protection efficiency: 1.031

## Gates G1–G6
- **Advisory readiness:** WATCH
- Gates passed: False
- Failed: G3

- **G1** (observations >= 30): PASS
- **G2** (best strategy total_value > 0): PASS
- **G3** (best strategy win_rate >= 0.60): FAIL
- **G4** (risk_of_cutting_winners <= 0.35): PASS
- **G5** (best strategy beats HOLD by positive margin): PASS
- **G6** (no single ticker contributes >50% of best strategy total): PASS

## Ticker findings

- **MU** — obs=7, missed=1402.77 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **AMAT** — obs=5, missed=1112.55 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **HSBA.L** — obs=4, missed=940.99 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **LLY** — obs=11, missed=540.26 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **PM** — obs=11, missed=362.2 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **AZN.L** — obs=5, missed=228.87 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **SPY** — obs=10, missed=198.96 USD, best=shadow_trailing_1, rec=AVOID_PROTECTION_FOR_NOW
- **SIE.DE** — obs=6, missed=191.18 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **MRK** — obs=10, missed=132.12 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **MC.PA** — obs=10, missed=106.85 USD, best=shadow_trailing_1, rec=AVOID_PROTECTION_FOR_NOW

## Daily findings

- **2026-06-30** (wrapper_run) — missed=133.49, best=78.0, hold=4.5, SHADOW_OUTPERFORMS_HOLD
- **2026-07-01** (20260701T225031) — missed=456.52, best=248.1, hold=-8.28, SHADOW_OUTPERFORMS_HOLD
- **2026-07-01** (20260701T232612) — missed=486.76, best=252.95, hold=-33.35, SHADOW_OUTPERFORMS_HOLD
- **2026-07-03** (20260703T160710) — missed=155.94, best=288.89, hold=253.69, SHADOW_OUTPERFORMS_HOLD
- **2026-07-03** (20260703T160719) — missed=155.94, best=288.89, hold=253.69, SHADOW_OUTPERFORMS_HOLD
- **2026-07-03** (20260703T162638) — missed=153.01, best=287.14, hold=256.63, SHADOW_OUTPERFORMS_HOLD
- **2026-07-05** (20260705T204352) — missed=575.34, best=642.67, hold=223.89, SHADOW_OUTPERFORMS_HOLD
- **2026-07-06** (20260706T125406) — missed=828.1, best=881.93, hold=252.74, SHADOW_OUTPERFORMS_HOLD
- **2026-07-06** (20260706T130245) — missed=828.78, best=875.91, hold=252.05, SHADOW_OUTPERFORMS_HOLD
- **2026-07-06** (20260706T130716) — missed=829.08, best=878.16, hold=251.76, SHADOW_OUTPERFORMS_HOLD
- **2026-07-06** (20260706T131033) — missed=829.72, best=878.54, hold=251.1, SHADOW_OUTPERFORMS_HOLD

## Recommendations (SHADOW_ONLY)

- DO_NOT_PROMOTE_TO_ADVISORY_YET
- TEST_TRAILING_SHADOW

## Final verdict
- PROMISING_BUT_NOT_READY
- Next step: Proceed to X.COOLDOWN-1 if BUY→STOP→BUY churn observed in portfolio.

*No live BUY/SELL. Research validation only.*
