# TAE Intraday Discovery Engine

**Generated:** 2026-07-01T22:57:41
**Mode:** SHADOW_ONLY — NONE

## Dataset health
- Observations: **14**
- Unique days: **2**
- Unique tickers: **12**
- Data quality: **GOOD**
- Minimum sample warning: **True**

## Top tickers by missed opportunity
- **PM**: total missed 129.84 USD, sig fade rate 1.0, confidence LOW
- **LLY**: total missed 121.43 USD, sig fade rate 0.0, confidence LOW
- **MU**: total missed 115.1 USD, sig fade rate 0.0, confidence LOW
- **AZN.L**: total missed 61.74 USD, sig fade rate 0.0, confidence LOW
- **MRK**: total missed 58.92 USD, sig fade rate 0.0, confidence LOW
- **SIE.DE**: total missed 56.3 USD, sig fade rate 1.0, confidence LOW
- **AAPL**: total missed 21.24 USD, sig fade rate 0.0, confidence LOW
- **SPY**: total missed 10.09 USD, sig fade rate 0.0, confidence LOW
- **ULVR.L**: total missed 9.31 USD, sig fade rate 0.0, confidence LOW
- **PG**: total missed 2.69 USD, sig fade rate 0.0, confidence LOW

## Patterns discovered
- `LOW_CONFIDENCE_INSUFFICIENT_SAMPLE` [all]: observations=14 (confidence LOW)
- `BEST_SHADOW_TRAILING` [shadow_trailing_1]: cumulative_shadow_pnl_usd=448.1 (confidence MEDIUM)
- `HIGH_FADE_TICKER` [PM]: total_missed_opportunity=129.84 (confidence LOW)
- `HIGH_FADE_TICKER` [LLY]: total_missed_opportunity=121.43 (confidence LOW)

## Recommendations (SHADOW_ONLY)
- **INSUFFICIENT_DATA** — Only 14 observations; need 30+ for reliable learning.
- **TEST_TRAILING_SHADOW** — Detected from test trailing shadow patterns.
- **PRIORITIZE_TRACKING** — Detected from prioritize tracking patterns.
