# TAE Rule Survival Report

**Generated:** 2026-09-03T13:02:33+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Source:** `runtime_outputs/paper_execution/rule_outcome_attribution.json`

## State counts

- **NEW**: 0
- **TESTING**: 20
- **ACTIVE**: 3
- **TRUSTED**: 1
- **WATCHLIST**: 1
- **DEPRECATED**: 0
- **DISABLED**: 2

## Rules by state

### TESTING

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| DO_NOT_PROMOTE_TO_LIVE | 41.7% | $484.92 | $2.89 | mixed evidence win_rate=41.7% net_pnl=$484.92 |
| KNOW-HOLD_PAPER | 41.7% | $484.92 | $2.89 | mixed evidence win_rate=41.7% net_pnl=$484.92 |
| KNOW-SELL_PAPER | 38.1% | $-174.33 | $-1.80 | mixed evidence win_rate=38.1% net_pnl=$-174.33 |
| LTB-CONF-MISSED_PROFIT_PROTECTION | 40.0% | $44.94 | $4.49 | mixed evidence win_rate=40.0% net_pnl=$44.94 |
| LTB-CONF-SCORE_PERSISTENCE_AFTER_ | 40.0% | $44.94 | $4.49 | mixed evidence win_rate=40.0% net_pnl=$44.94 |
| LTB-CONF-STOP_REENTRY_CHURN | 40.0% | $44.94 | $4.49 | mixed evidence win_rate=40.0% net_pnl=$44.94 |
| LTB-DPE-PHIL-001 | 41.6% | $529.86 | $2.98 | mixed evidence win_rate=41.6% net_pnl=$529.86 |
| LTB-LIFE-LLY-05 | 0.0% | $-27.10 | $-27.10 | insufficient evidence (1<5) |
| LTB-LIFE-MRK-01 | 100.0% | $6.20 | $3.10 | insufficient evidence (2<5) |
| LTB-LOSS-LOSS-CRYSTALLIZATION-ABF990 | 36.6% | $-1,078.02 | $-13.15 | mixed evidence win_rate=36.6% net_pnl=$-1078.02 |
| LTB-OPP-HSBA.L-01 | 25.0% | $2.19 | $0.55 | insufficient evidence (4<5) |
| LTB-PATTERN-001 | 41.7% | $484.92 | $2.89 | mixed evidence win_rate=41.7% net_pnl=$484.92 |
| LTB-PROT-ALV.DE | 100.0% | $37.30 | $37.30 | insufficient evidence (1<5) |
| LTB-PROT-PPG-HSBA.L | 0.0% | $0.00 | $0.00 | insufficient evidence (3<5) |
| LTB-PROT-PPG-MC.PA | 0.0% | $0.00 | $0.00 | insufficient evidence (3<5) |

### ACTIVE

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| KNOW-BUY_PAPER | 46.6% | $1,521.20 | $12.89 | win_rate=46.6% net_pnl=$1521.20 |
| KNOW-PROTECT_PAPER | 49.3% | $927.11 | $13.06 | win_rate=49.3% net_pnl=$927.11 |
| TAE_SHADOW_SIZING_COMPARISON_V1 | 47.6% | $1,499.77 | $18.29 | win_rate=47.6% net_pnl=$1499.77 |

### TRUSTED

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-PG-02 | 100.0% | $1,178.56 | $107.14 | win_rate=100.0% avg_pnl=$107.14 n=11 |

### WATCHLIST

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| SCORE_DECAY_SHADOW | 16.7% | $-1.76 | $-0.29 | win_rate=16.7% net_pnl=$-1.76 |

### DISABLED

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-LLY-04 | 0.0% | $-325.25 | $-27.10 | win_rate=0.0% net_pnl=$-325.25 n=12 |
| LTB-LIFE-PM-05 | 0.0% | $-2,163.64 | $-98.35 | win_rate=0.0% net_pnl=$-2163.64 n=22 |

## Lifecycle influence multipliers

| state | multiplier | effect |
| --- | --- | --- |
| DISABLED | 0.0 | cannot increase action score |
| DEPRECATED | 0.12 | strongly reduced |
| WATCHLIST | 0.45 | reduced |
| TESTING | 0.85 | cautious |
| ACTIVE | 1.0 | neutral |
| TRUSTED | 1.06 | modest boost (capped) |
