# TAE Conflict Resolution Report

**Generated:** 2026-09-11T14:01:55+00:00
**Mode:** PAPER_ONLY — evidence orchestrator — NO_BROKER — NO_LIVE_PROMOTION
**Reconciliation:** PASS — reconciliation gate

## Executive summary

- Tickers analyzed: **98**
- Policy state: **WATCH**
- Cash hint: **$129.33**
- BUY blocked despite cash (positive BUY EV): **0**
- STRONG BUY → SKIP cases: **0**
- Switch authorized: **66**
- Switch blocked (decision state): **0**

## Switch gating sample

| ticker | prev | winner | authorized | hard bypass | cooldown | churn | EV act/req |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| ABBV | BUY_PAPER | SELL_PAPER | yes | no | no | HIGH | 7.3039 / 0.15 |
| ADBE | BUY_PAPER | SKIP_PAPER | yes | no | no | HIGH | -1.0 / 0.15 |
| ADI | BUY_PAPER | SKIP_PAPER | yes | no | no | LOW | -1.0 / 0.15 |
| ADSK | BUY_PAPER | SKIP_PAPER | yes | no | no | HIGH | -1.0 / 0.15 |
| AIG | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| AIR.PA | SELL_PAPER | SKIP_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| ALL | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| ALV.DE | BUY_PAPER | SELL_PAPER | yes | no | no | HIGH | 1.99 / 0.15 |
| AMAT | SELL_PAPER | BUY_PAPER | yes | no | no | HIGH | 1.4087 / 0.15 |
| AMD | BUY_PAPER | SELL_PAPER | yes | no | no | HIGH | 0.7174 / 0.15 |

## Top conflicts

| ticker | winner | authority | explanation |
| --- | --- | --- | --- |
| AAPL | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.294; authority=EV_OPTIMIZER; prob=0.5746; BUY blockers=L |
| ABBV | SELL_PAPER | EV_OPTIMIZER | winner=SELL_PAPER raEV=25.2772; authority=EV_OPTIMIZER; prob=0.6691; BUY blocker |
| ADBE | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.5834; BUY blockers |
| ADI | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.5506; BUY blockers |
| ADSK | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.5834; BUY blockers |
| AFL | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.5506; BUY blockers |
| AIG | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.294; authority=EV_OPTIMIZER; prob=0.5746; BUY blockers=L |
| AIR.PA | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.1725; authority=POLICY_CAUTION; prob=0.5629; BUY block |
| ALL | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.294; authority=EV_OPTIMIZER; prob=0.5746; BUY blockers=L |
| ALV.DE | SELL_PAPER | EV_OPTIMIZER | winner=SELL_PAPER raEV=9.7744; authority=EV_OPTIMIZER; prob=0.6691; BUY blockers |
| AMAT | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=0.705; authority=EV_OPTIMIZER; prob=0.553; BUY blockers=LO |
| AMD | SELL_PAPER | EV_OPTIMIZER | winner=SELL_PAPER raEV=5.2277; authority=EV_OPTIMIZER; prob=0.6691; BUY blockers |

## EV table sample (first 8 tickers)

### AAPL → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5746 | 2.294 | LOW_CASH_HINT |
| HOLD_PAPER | 0.78 | 3.0 | 0.6691 | -2.9297 | - |
| PROTECT_PAPER | 2.43 | 12.75 | 0.5834 | -13.2448 | - |
| REDUCE_PAPER | 1.94 | 10.2 | 0.6119 | -10.5405 | - |
| ROTATE_PAPER | 1.75 | 6.6 | 0.6119 | -6.5194 | - |
| SELL_PAPER | 10.43 | 5.95 | 0.6691 | 0.1369 | - |
| SKIP_PAPER | 0.0 | 1.0932 | 0.5834 | -0.3143 | - |

### ABBV → SELL_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.6246 | 3.044 | LOW_CASH_HINT |
| HOLD_PAPER | 0.0 | 3.0 | 0.6691 | -3.45 | - |
| PROTECT_PAPER | 0.0 | 12.75 | 0.5834 | -14.6625 | - |
| REDUCE_PAPER | 0.0 | 10.2 | 0.6119 | -11.73 | - |
| ROTATE_PAPER | 0.0 | 6.6 | 0.6119 | -7.59 | - |
| SELL_PAPER | 37.78 | 0.0 | 0.6691 | 25.2772 | - |
| SKIP_PAPER | 0.0 | 0.0 | 0.5834 | -0.0 | - |

### ADBE → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5246 | 1.544 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.5834 | -0.0 | - |

### ADI → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5452 | 1.853 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.5506 | -0.0 | - |

### ADSK → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5246 | 1.544 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.5834 | -0.0 | - |

### AFL → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5452 | 1.853 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.5506 | -0.0 | - |

### AIG → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5746 | 2.294 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.5834 | -0.0 | - |

### AIR.PA → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.513 | 1.37 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.6 | 0.5629 | -0.1725 | - |

## Safety

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| NO_BROKER | ✅ |
| live_promotion_allowed | **false** |
| Overrides hard rules | **false** |
