# TAE Rule Survival Report

**Generated:** 2026-09-12T15:02:02+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Source:** `runtime_outputs/paper_execution/rule_outcome_attribution.json`

## State counts

- **NEW**: 0
- **TESTING**: 9
- **ACTIVE**: 9
- **TRUSTED**: 2
- **WATCHLIST**: 6
- **DEPRECATED**: 1
- **DISABLED**: 1

## Rules by state

### TESTING

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-LLY-05 | 0.0% | $-4.84 | $-4.84 | insufficient evidence (1<5) |
| LTB-LOSS-LOSS-CRYSTALLIZATION-ABF990 | 52.6% | $-12.13 | $-0.08 | mixed evidence win_rate=52.6% net_pnl=$-12.13 |
| LTB-PROT-ALV.DE | 100.0% | $12.52 | $12.52 | insufficient evidence (1<5) |
| LTB-PROT-PPG-HSBA.L | 100.0% | $15.60 | $3.90 | insufficient evidence (4<5) |
| LTB-PROT-PPG-MC.PA | 0.0% | $0.00 | $0.00 | insufficient evidence (3<5) |
| LTB-PROT-PPG-QQQ | 0.0% | $-1.50 | $-1.50 | insufficient evidence (1<5) |
| LTB-PROT-PPG-ULVR.L | 0.0% | $-20.46 | $-20.46 | insufficient evidence (1<5) |
| LTB-PROT-ULVR.L | 0.0% | $-20.46 | $-20.46 | insufficient evidence (1<5) |
| TAE_SHADOW_SIZING_COMPARISON_V1 | 43.4% | $673.93 | $3.44 | mixed evidence win_rate=43.4% net_pnl=$673.93 |

### ACTIVE

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| DO_NOT_PROMOTE_TO_LIVE | 47.8% | $657.15 | $1.84 | win_rate=47.8% net_pnl=$657.15 |
| KNOW-BUY_PAPER | 45.4% | $1,328.05 | $4.53 | win_rate=45.4% net_pnl=$1328.05 |
| KNOW-HOLD_PAPER | 47.8% | $657.15 | $1.84 | win_rate=47.8% net_pnl=$657.15 |
| KNOW-PROTECT_PAPER | 54.9% | $175.32 | $2.47 | win_rate=54.9% net_pnl=$175.32 |
| KNOW-SELL_PAPER | 46.0% | $479.10 | $1.67 | win_rate=46.0% net_pnl=$479.10 |
| LTB-DPE-PHIL-001 | 47.0% | $646.56 | $1.76 | win_rate=47.0% net_pnl=$646.56 |
| LTB-OPP-HSBA.L-01 | 100.0% | $19.50 | $3.90 | win_rate=100.0% net_pnl=$19.50 |
| LTB-PATTERN-001 | 47.8% | $657.15 | $1.84 | win_rate=47.8% net_pnl=$657.15 |
| LTB-STALE-001 | 47.0% | $646.56 | $1.76 | win_rate=47.0% net_pnl=$646.56 |

### TRUSTED

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-PG-02 | 100.0% | $135.86 | $12.35 | win_rate=100.0% avg_pnl=$12.35 n=11 |
| LTB-LIFE-PM-05 | 100.0% | $265.83 | $11.56 | win_rate=100.0% avg_pnl=$11.56 n=23 |

### WATCHLIST

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-CONF-MISSED_PROFIT_PROTECTION | 20.0% | $-10.59 | $-1.06 | win_rate=20.0% net_pnl=$-10.59 |
| LTB-CONF-SCORE_PERSISTENCE_AFTER_ | 20.0% | $-10.59 | $-1.06 | win_rate=20.0% net_pnl=$-10.59 |
| LTB-CONF-STOP_REENTRY_CHURN | 20.0% | $-10.59 | $-1.06 | win_rate=20.0% net_pnl=$-10.59 |
| LTB-REPLAY-04 | 20.0% | $-10.59 | $-1.06 | win_rate=20.0% net_pnl=$-10.59 |
| MISSED_PROFIT_PROTECTION | 20.0% | $-10.59 | $-1.06 | win_rate=20.0% net_pnl=$-10.59 |
| SCORE_DECAY_SHADOW | 0.0% | $-1.71 | $-0.28 | win_rate=0.0% net_pnl=$-1.71 |

### DEPRECATED

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-LLY-04 | 0.0% | $-62.98 | $-4.84 | win_rate=0.0% net_pnl=$-62.98 |

### DISABLED

| rule | win_rate | net_pnl | avg_pnl | reason |
| --- | --- | --- | --- | --- |
| LTB-LIFE-MRK-01 | 0.0% | $-1,020.99 | $-85.08 | win_rate=0.0% net_pnl=$-1020.99 n=12 |

## Lifecycle influence multipliers

| state | multiplier | effect |
| --- | --- | --- |
| DISABLED | 0.0 | cannot increase action score |
| DEPRECATED | 0.12 | strongly reduced |
| WATCHLIST | 0.45 | reduced |
| TESTING | 0.85 | cautious |
| ACTIVE | 1.0 | neutral |
| TRUSTED | 1.06 | modest boost (capped) |
