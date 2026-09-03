# TAE Conflict Resolution Report

**Generated:** 2026-09-03T13:02:35+00:00
**Mode:** PAPER_ONLY — evidence orchestrator — NO_BROKER — NO_LIVE_PROMOTION
**Reconciliation:** PASS — reconciliation gate

## Executive summary

- Tickers analyzed: **98**
- Policy state: **WATCH**
- Cash hint: **$94.58**
- BUY blocked despite cash (positive BUY EV): **0**
- STRONG BUY → SKIP cases: **0**
- Switch authorized: **50**
- Switch blocked (decision state): **0**

## Switch gating sample

| ticker | prev | winner | authorized | hard bypass | cooldown | churn | EV act/req |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL | BUY_PAPER | SELL_PAPER | yes | no | no | HIGH | 21.6196 / 0.15 |
| ABBV | BUY_PAPER | SELL_PAPER | yes | no | no | HIGH | 4.4555 / 0.15 |
| ADBE | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| ADI | BUY_PAPER | SKIP_PAPER | yes | no | no | LOW | -1.0 / 0.15 |
| ADSK | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| AIG | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| AIR.PA | SELL_PAPER | SKIP_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| ALL | BUY_PAPER | BUY_PAPER | yes | no | no | MEDIUM | 0.0 / 0.15 |
| ALV.DE | BUY_PAPER | SELL_PAPER | yes | no | no | HIGH | 6.0809 / 0.15 |
| AMAT | SELL_PAPER | BUY_PAPER | yes | no | no | HIGH | 1.4609 / 0.15 |
| AMD | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |

## Top conflicts

| ticker | winner | authority | explanation |
| --- | --- | --- | --- |
| AAPL | SELL_PAPER | EV_OPTIMIZER | winner=SELL_PAPER raEV=44.5606; authority=EV_OPTIMIZER; prob=0.6212; BUY blocker |
| ABBV | SELL_PAPER | EV_OPTIMIZER | winner=SELL_PAPER raEV=17.163; authority=EV_OPTIMIZER; prob=0.6438; BUY blockers |
| ADBE | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=3.0845; authority=EV_OPTIMIZER; prob=0.6273; BUY blockers= |
| ADI | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.56; BUY blockers=L |
| ADSK | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.396; authority=EV_OPTIMIZER; prob=0.5814; BUY blockers=L |
| AFL | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.56; BUY blockers=L |
| AIG | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.399; authority=EV_OPTIMIZER; prob=0.5816; BUY blockers=L |
| AIR.PA | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.1725; authority=POLICY_CAUTION; prob=0.57; BUY blocker |
| ALL | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.8265; authority=EV_OPTIMIZER; prob=0.6101; BUY blockers= |
| ALV.DE | SELL_PAPER | EV_OPTIMIZER | winner=SELL_PAPER raEV=24.0929; authority=EV_OPTIMIZER; prob=0.6459; BUY blocker |
| AMAT | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=0.795; authority=EV_OPTIMIZER; prob=0.559; BUY blockers=LO |
| AMD | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.396; authority=EV_OPTIMIZER; prob=0.5814; BUY blockers=L |

## EV table sample (first 8 tickers)

### AAPL → SELL_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.553 | 1.97 | LOW_CASH_HINT |
| HOLD_PAPER | 0.78 | 3.0 | 0.66 | -2.9368 | - |
| PROTECT_PAPER | 2.43 | 12.75 | 0.56 | -13.3017 | - |
| REDUCE_PAPER | 1.94 | 10.2 | 0.5933 | -10.5766 | - |
| ROTATE_PAPER | 1.75 | 6.6 | 0.5933 | -6.552 | - |
| SELL_PAPER | 82.75 | 5.95 | 0.6212 | 44.5606 | - |
| SKIP_PAPER | 0.0 | 1.0932 | 0.56 | -0.3143 | - |

### ABBV → SELL_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.6314 | 3.146 | LOW_CASH_HINT |
| HOLD_PAPER | 0.0 | 3.0 | 0.6771 | -3.45 | - |
| PROTECT_PAPER | 0.0 | 12.75 | 0.5914 | -14.6625 | - |
| REDUCE_PAPER | 0.0 | 10.2 | 0.62 | -11.73 | - |
| ROTATE_PAPER | 0.0 | 6.6 | 0.62 | -7.59 | - |
| SELL_PAPER | 26.66 | 0.0 | 0.6438 | 17.163 | - |
| SKIP_PAPER | 0.0 | 0.0 | 0.5914 | -0.0 | - |

### ADBE → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.6273 | 3.0845 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.56 | -0.0 | - |

### ADI → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.4958 | 1.112 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.56 | -0.0 | - |

### ADSK → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5814 | 2.396 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.5914 | -0.0 | - |

### AFL → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.4958 | 1.112 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.56 | -0.0 | - |

### AIG → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5816 | 2.399 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.56 | -0.0 | - |

### AIR.PA → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.519 | 1.46 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.6 | 0.57 | -0.1725 | - |

## Safety

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| NO_BROKER | ✅ |
| live_promotion_allowed | **false** |
| Overrides hard rules | **false** |
