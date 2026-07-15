# TAE ROI-001 Challenger Report

**Generated:** 2026-07-15T20:24:22+00:00
**ROI_ID:** ROI-001 · PTA_PARTIAL_SIZE_TO_REDUCE_TRIM
**Verdict:** `ROI001_NEEDS_MORE_EVIDENCE`
**Commit:** NO · baseline restored: **True**

Construction frozen. No new engine/strategy/signals. Production default remains **baseline**.

---

## Rules compared

- **Baseline:** `trim_pct = 30 if confidence < 0.7 else 20`
- **Challenger:** `trim_pct = PTA suggested_partial_size_pct (else baseline fallback)`

## Sample

- REDUCE executions: **4** (need ≥10)
- Tickers: **AAPL, GE, HSBA.L, PG** (count 4, need ≥3)

## Per-opportunity comparison

| Ticker | Base % | Chal % | Shares Δ | Cash Δ | Realized Δ | Remain UPNL Δ |
|--------|-------:|-------:|---------:|-------:|-----------:|--------------:|
| HSBA.L | 20 | 50 | 0.4173 | 617.53 | 5.9257 | -5.9257 |
| PG | 20 | 20 | 0.0000 | 0.00 | 0.0000 | 0.0000 |
| AAPL | 20 | 25 | 0.4050 | 132.74 | 5.9881 | -5.9881 |
| GE | 30 | 25 | -0.0644 | -23.12 | 0.0078 | -0.0077 |

## BASELINE vs CHALLENGER

| Metric | Baseline | Challenger | Delta |
|--------|----------:|-----------:|------:|
| Realized PnL (REDUCE legs) | 30.3491 | 42.2707 | 11.9216 |
| Cash released | 1580.2418 | 2307.3928 | 727.1510 |
| Remaining UPNL (legs) | 121.4737 | 109.5522 | -11.9215 |
| Remaining position value | 6089.7968 | 5362.6459 | -727.1509 |
| Portfolio value | 29819.1164 | 29819.1164 | 0.0000 |
| Drawdown % | 1.719802 | 1.514449 | -0.205353 |
| Expectancy | 7.587275 | 10.567675 | 2.980400 |
| Profit Factor | 655.075431 | 1096.095855 | 441.020424 |
| Capital efficiency | 0.019205 | 0.018320 | -0.000886 |

## Promotion checks

| Check | Pass |
|-------|:----:|
| `higher_realized_profit` | PASS |
| `drawdown_le_baseline` | PASS |
| `profit_factor_ge_baseline` | PASS |
| `expectancy_ge_baseline` | PASS |
| `min_reduce_executions` | FAIL |
| `min_tickers` | PASS |
| `hard_risk_regression` | PASS |
| `decision_state_regression` | PASS |
| `duplicate_execution` | PASS |
| `profit_integrity_pass` | PASS |
| `reconciliation_pass` | PASS |
| `production_default_unchanged` | PASS |

## Integrity

- Profit Integrity: **PAPER_PROFIT_INTEGRITY_CLOSED** ok=True
- Reconciliation: **PASS**

## Final verdict

```
ROI001_NEEDS_MORE_EVIDENCE
```


Challenger sized legs improve realized/expectancy/PF on available history, but sample < 10 REDUCE executions — promotion blocked.

