# TAE Conflict Resolution Report

**Generated:** 2026-09-12T15:02:07+00:00
**Mode:** PAPER_ONLY — evidence orchestrator — NO_BROKER — NO_LIVE_PROMOTION
**Reconciliation:** PASS — reconciliation gate

## Executive summary

- Tickers analyzed: **98**
- Policy state: **WATCH**
- Cash hint: **$196.27**
- BUY blocked despite cash (positive BUY EV): **0**
- STRONG BUY → SKIP cases: **0**
- Switch authorized: **62**
- Switch blocked (decision state): **0**

## Switch gating sample

| ticker | prev | winner | authorized | hard bypass | cooldown | churn | EV act/req |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL | BUY_PAPER | HOLD_PAPER | yes | no | no | HIGH | -2.3117 / 0.15 |
| ABBV | BUY_PAPER | SELL_PAPER | yes | no | no | HIGH | 1.9308 / 0.15 |
| ADBE | BUY_PAPER | SKIP_PAPER | yes | no | no | HIGH | -1.0 / 0.15 |
| ADI | BUY_PAPER | BUY_PAPER | yes | no | no | MEDIUM | 0.0 / 0.15 |
| ADSK | BUY_PAPER | SKIP_PAPER | yes | no | no | HIGH | -1.0 / 0.15 |
| AIG | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| AIR.PA | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| ALL | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| ALV.DE | BUY_PAPER | SELL_PAPER | yes | no | no | HIGH | 1.583 / 0.15 |
| AMAT | SELL_PAPER | BUY_PAPER | yes | no | no | HIGH | 1.3783 / 0.15 |
| AMD | BUY_PAPER | HOLD_PAPER | yes | no | no | HIGH | -2.1556 / 0.15 |

## Top conflicts

| ticker | winner | authority | explanation |
| --- | --- | --- | --- |
| AAPL | HOLD_PAPER | POLICY_CAUTION | winner=HOLD_PAPER raEV=-2.9324; authority=POLICY_CAUTION; prob=0.6657; BUY block |
| ABBV | SELL_PAPER | EV_OPTIMIZER | winner=SELL_PAPER raEV=8.75; authority=EV_OPTIMIZER; prob=0.6621; BUY blockers=L |
| ADBE | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.58; BUY blockers=L |
| ADI | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.9015; authority=EV_OPTIMIZER; prob=0.6151; BUY blockers= |
| ADSK | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.58; BUY blockers=L |
| AFL | SKIP_PAPER | POLICY_CAUTION | winner=SKIP_PAPER raEV=-0.0; authority=POLICY_CAUTION; prob=0.5466; BUY blockers |
| AIG | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.2355; authority=EV_OPTIMIZER; prob=0.5707; BUY blockers= |
| AIR.PA | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=1.985; authority=EV_OPTIMIZER; prob=0.554; BUY blockers=LO |
| ALL | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.2355; authority=EV_OPTIMIZER; prob=0.5707; BUY blockers= |
| ALV.DE | SELL_PAPER | EV_OPTIMIZER | winner=SELL_PAPER raEV=8.2927; authority=EV_OPTIMIZER; prob=0.6621; BUY blockers |
| AMAT | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=0.6525; authority=EV_OPTIMIZER; prob=0.5495; BUY blockers= |
| AMD | HOLD_PAPER | POLICY_CAUTION | winner=HOLD_PAPER raEV=-3.45; authority=POLICY_CAUTION; prob=0.6657; BUY blocker |

## EV table sample (first 8 tickers)

### AAPL → HOLD_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5707 | 2.2355 | LOW_CASH_HINT |
| HOLD_PAPER | 0.78 | 3.0 | 0.6657 | -2.9324 | - |
| PROTECT_PAPER | 2.43 | 12.75 | 0.58 | -13.2531 | - |
| REDUCE_PAPER | 1.94 | 10.2 | 0.6085 | -10.5471 | - |
| ROTATE_PAPER | 1.75 | 6.6 | 0.6085 | -6.5254 | - |
| SELL_PAPER | 10.84 | 5.95 | 0.6621 | 0.3361 | - |
| SKIP_PAPER | 0.0 | 1.0932 | 0.58 | -0.3143 | - |

### ABBV → SELL_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.6207 | 2.9855 | LOW_CASH_HINT |
| HOLD_PAPER | 0.0 | 3.0 | 0.6657 | -3.45 | - |
| PROTECT_PAPER | 0.0 | 12.75 | 0.58 | -14.6625 | - |
| REDUCE_PAPER | 0.0 | 10.2 | 0.6085 | -11.73 | - |
| ROTATE_PAPER | 0.0 | 6.6 | 0.6085 | -7.59 | - |
| SELL_PAPER | 13.22 | 0.0 | 0.6621 | 8.75 | - |
| SKIP_PAPER | 0.0 | 0.0 | 0.58 | -0.0 | - |

### ADBE → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5207 | 1.4855 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.58 | -0.0 | - |

### ADI → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.6151 | 2.9015 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.5466 | -0.0 | - |

### ADSK → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5207 | 1.4855 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.58 | -0.0 | - |

### AFL → SKIP_PAPER (POLICY_CAUTION)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5408 | 1.787 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.5466 | -0.0 | - |

### AIG → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.5707 | 2.2355 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.0 | 0.58 | -0.0 | - |

### AIR.PA → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.554 | 1.985 | LOW_CASH_HINT |
| SKIP_PAPER | 0.0 | 0.6 | 0.56 | -0.1725 | - |

## Safety

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| NO_BROKER | ✅ |
| live_promotion_allowed | **false** |
| Overrides hard rules | **false** |
