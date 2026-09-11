# TAE Rule Survival Report

**Generated:** 2026-09-11T14:01:50+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Source:** `runtime_outputs/paper_execution/rule_outcome_attribution.json`

## State counts

- **NEW**: 0
- **TESTING**: 13
- **ACTIVE**: 11
- **TRUSTED**: 1
- **WATCHLIST**: 1
- **DEPRECATED**: 0
- **DISABLED**: 2

## Rules by state

### TESTING

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-CONF-MISSED_PROFIT_PROTECTION | 30.0% | $4.11 | $0.41 | mixed evidence win_rate=30.0% net_pnl=$4.11 |
| LTB-CONF-SCORE_PERSISTENCE_AFTER_ | 30.0% | $4.11 | $0.41 | mixed evidence win_rate=30.0% net_pnl=$4.11 |
| LTB-CONF-STOP_REENTRY_CHURN | 30.0% | $4.11 | $0.41 | mixed evidence win_rate=30.0% net_pnl=$4.11 |
| LTB-LIFE-LLY-05 | 0.0% | $-3.52 | $-3.52 | insufficient evidence (1<5) |
| LTB-PROT-ALV.DE | 100.0% | $14.61 | $14.61 | insufficient evidence (1<5) |
| LTB-PROT-PPG-HSBA.L | 100.0% | $17.17 | $4.29 | insufficient evidence (4<5) |
| LTB-PROT-PPG-MC.PA | 0.0% | $0.00 | $0.00 | insufficient evidence (3<5) |
| LTB-PROT-PPG-QQQ | 0.0% | $-0.53 | $-0.53 | insufficient evidence (1<5) |
| LTB-PROT-PPG-ULVR.L | 0.0% | $-14.38 | $-14.38 | insufficient evidence (1<5) |
| LTB-PROT-ULVR.L | 0.0% | $-14.38 | $-14.38 | insufficient evidence (1<5) |
| LTB-REPLAY-04 | 30.0% | $4.11 | $0.41 | mixed evidence win_rate=30.0% net_pnl=$4.11 |
| MISSED_PROFIT_PROTECTION | 30.0% | $4.11 | $0.41 | mixed evidence win_rate=30.0% net_pnl=$4.11 |
| SCORE_DECAY_SHADOW | 16.7% | $3.11 | $0.52 | mixed evidence win_rate=16.7% net_pnl=$3.11 |

### ACTIVE

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| DO_NOT_PROMOTE_TO_LIVE | 55.8% | $1,066.65 | $3.00 | win_rate=55.8% net_pnl=$1066.65 |
| KNOW-BUY_PAPER | 59.0% | $2,205.40 | $7.61 | win_rate=59.0% net_pnl=$2205.40 |
| KNOW-HOLD_PAPER | 55.8% | $1,066.65 | $3.00 | win_rate=55.8% net_pnl=$1066.65 |
| KNOW-PROTECT_PAPER | 56.3% | $160.62 | $2.26 | win_rate=56.3% net_pnl=$160.62 |
| KNOW-SELL_PAPER | 55.6% | $904.26 | $3.18 | win_rate=55.6% net_pnl=$904.26 |
| LTB-DPE-PHIL-001 | 55.1% | $1,070.76 | $2.93 | win_rate=55.1% net_pnl=$1070.76 |
| LTB-LOSS-LOSS-CRYSTALLIZATION-ABF990 | 55.7% | $278.73 | $1.87 | win_rate=55.7% net_pnl=$278.73 |
| LTB-OPP-HSBA.L-01 | 100.0% | $21.47 | $4.29 | win_rate=100.0% net_pnl=$21.47 |
| LTB-PATTERN-001 | 55.8% | $1,066.65 | $3.00 | win_rate=55.8% net_pnl=$1066.65 |
| LTB-STALE-001 | 55.1% | $1,070.76 | $2.93 | win_rate=55.1% net_pnl=$1070.76 |
| TAE_SHADOW_SIZING_COMPARISON_V1 | 56.4% | $796.70 | $3.94 | win_rate=56.4% net_pnl=$796.70 |

### TRUSTED

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-PM-05 | 100.0% | $261.74 | $11.38 | win_rate=100.0% avg_pnl=$11.38 n=23 |

### WATCHLIST

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-LLY-04 | 0.0% | $-45.81 | $-3.52 | win_rate=0.0% net_pnl=$-45.81 |

### DISABLED

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-MRK-01 | 0.0% | $-858.67 | $-71.56 | win_rate=0.0% net_pnl=$-858.67 n=12 |
| LTB-LIFE-PG-02 | 0.0% | $-510.88 | $-46.44 | win_rate=0.0% net_pnl=$-510.88 n=11 |

## Lifecycle influence multipliers

| state | multiplier | effect |
| --- | --- | --- |
| DISABLED | 0.0 | cannot increase action score |
| DEPRECATED | 0.12 | strongly reduced |
| WATCHLIST | 0.45 | reduced |
| TESTING | 0.85 | cautious |
| ACTIVE | 1.0 | neutral |
| TRUSTED | 1.06 | modest boost (capped) |
