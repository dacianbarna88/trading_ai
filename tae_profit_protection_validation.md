# TAE Profit Protection Historical Validation (X.PROTECT-2)

**Generated:** 2026-07-02T13:59:34
**Mode:** SHADOW_ONLY | **Verdict:** PROMISING_BUT_NOT_READY

## Dataset health
- Observations: **26**
- Unique days: 2 | Tickers: 12
- Date range: ['2026-06-30', '2026-07-01']
- Data quality: LIMITED
- Confidence: **LOW**
- Minimum sample warning: True

## Strategy ranking

| Strategy | Total | Δ vs HOLD | Win rate | Cut winners rate |
|----------|-------|-----------|----------|------------------|
| shadow_trailing_1 | 579.05 | 616.18 | 54% | 4% |
| shadow_trailing_1_5 | 421.61 | 458.74 | 54% | 4% |
| shadow_sell_30 | 324.3 | 361.43 | 100% | 0% |
| shadow_sell_20 | 218.97 | 256.1 | 100% | 0% |
| HOLD | -37.13 | 0.0 | 0% | 0% |

## Best strategy
- **shadow_trailing_1** — total 579.05 USD
- HOLD baseline: -37.13 USD
- Protection efficiency: 0.5378

## Gates G1–G6
- **Advisory readiness:** NOT_READY
- Gates passed: False
- Failed: G1, G3

- **G1** (observations >= 30): FAIL
- **G2** (best strategy total_value > 0): PASS
- **G3** (best strategy win_rate >= 0.60): FAIL
- **G4** (risk_of_cutting_winners <= 0.35): PASS
- **G5** (best strategy beats HOLD by positive margin): PASS
- **G6** (no single ticker contributes >50% of best strategy total): PASS

## Ticker findings

- **MU** — obs=2, missed=269.72 USD, best=shadow_trailing_1, rec=INSUFFICIENT_DATA
- **PM** — obs=3, missed=184.2 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **LLY** — obs=3, missed=175.14 USD, best=shadow_trailing_1, rec=CONTINUE_OBSERVATION
- **AZN.L** — obs=2, missed=123.48 USD, best=shadow_trailing_1, rec=INSUFFICIENT_DATA
- **MRK** — obs=2, missed=118.04 USD, best=shadow_trailing_1, rec=INSUFFICIENT_DATA
- **SIE.DE** — obs=2, missed=112.6 USD, best=shadow_trailing_1, rec=INSUFFICIENT_DATA
- **AAPL** — obs=2, missed=41.2 USD, best=shadow_trailing_1, rec=INSUFFICIENT_DATA
- **SPY** — obs=2, missed=22.8 USD, best=shadow_trailing_1, rec=INSUFFICIENT_DATA
- **ULVR.L** — obs=2, missed=18.62 USD, best=shadow_trailing_1, rec=INSUFFICIENT_DATA
- **QQQ** — obs=2, missed=5.25 USD, best=shadow_trailing_1, rec=INSUFFICIENT_DATA

## Daily findings

- **2026-06-30** (wrapper_run) — missed=133.49, best=78.0, hold=4.5, SHADOW_OUTPERFORMS_HOLD
- **2026-07-01** (20260701T225031) — missed=456.52, best=248.1, hold=-8.28, SHADOW_OUTPERFORMS_HOLD
- **2026-07-01** (20260701T232612) — missed=486.76, best=252.95, hold=-33.35, SHADOW_OUTPERFORMS_HOLD

## Recommendations (SHADOW_ONLY)

- INSUFFICIENT_DATA
- DO_NOT_PROMOTE_TO_ADVISORY_YET
- CONTINUE_OBSERVATION
- TEST_TRAILING_SHADOW

## Final verdict
- PROMISING_BUT_NOT_READY
- Next step: Continue observation until >=30 observations; then re-run validation.

*No live BUY/SELL. Research validation only.*
