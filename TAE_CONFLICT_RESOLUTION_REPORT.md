# TAE Conflict Resolution Report

**Generated:** 2026-07-08T19:30:07+00:00
**Mode:** PAPER_ONLY — evidence orchestrator — NO_BROKER — NO_LIVE_PROMOTION
**Reconciliation:** PASS — reconciliation gate

## Executive summary

- Tickers analyzed: **25**
- Policy state: **HIGH_RISK**
- Cash hint: **$2,335.28**
- BUY blocked despite cash (positive BUY EV): **0**
- STRONG BUY → SKIP cases: **0**
- Switch authorized: **4**
- Switch blocked (decision state): **0**

## Switch gating sample

| ticker | prev | winner | authorized | hard bypass | cooldown | churn | EV act/req |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AIR.PA | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| AMAT | BUY_PAPER | SELL_PAPER | yes | yes | no | HIGH | -3.6183 / 0.15 |
| DIA | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| GE | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |
| HD | BUY_PAPER | BUY_PAPER | yes | no | no | HIGH | 0.0 / 0.15 |

## Top conflicts

| ticker | winner | authority | explanation |
| --- | --- | --- | --- |
| AAPL | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.4275; authority=EV_OPTIMIZER; prob=0.7835; BUY blockers= |
| AIR.PA | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.4364999999999997; authority=EV_OPTIMIZER; prob=0.7841; B |
| DIA | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.4364999999999997; authority=EV_OPTIMIZER; prob=0.7841; B |
| GE | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.3555; authority=EV_OPTIMIZER; prob=0.7787; BUY blockers= |
| HSBA.L | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=0.7995000000000001; authority=EV_OPTIMIZER; prob=0.7593; B |
| MU | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=0.9375; authority=EV_OPTIMIZER; prob=0.7685; BUY blockers= |
| QQQ | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=1.4000000000000004; authority=EV_OPTIMIZER; prob=0.715; BU |
| ABBV | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=1.2409999999999997; authority=EV_OPTIMIZER; prob=0.7044; B |
| ALV.DE | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=1.6115000000000004; authority=EV_OPTIMIZER; prob=0.7291; B |
| AZN.L | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=1.322; authority=EV_OPTIMIZER; prob=0.7098; BUY blockers=H |
| BP.L | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=1.7495000000000003; authority=EV_OPTIMIZER; prob=0.7383; B |
| HD | BUY_PAPER | EV_OPTIMIZER | winner=BUY_PAPER raEV=2.0629999999999997; authority=EV_OPTIMIZER; prob=0.7592; B |

## EV table sample (first 8 tickers)

### AAPL → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.7835 | 2.4275 | APPE_HIGH_RISK_POLICY,APPE_CAPITAL_PRESERVATION |
| HOLD_PAPER | 0.78 | 3.0 | 0.7498 | -2.867 | - |
| PROTECT_PAPER | 5.43 | 5.355 | 0.7641 | -2.0092 | - |
| REDUCE_PAPER | 5.43 | 5.355 | 0.7069 | -2.3198 | - |
| ROTATE_PAPER | 1.75 | 6.6 | 0.7069 | -6.3532 | - |
| SELL_PAPER | 0.97 | 5.95 | 0.7069 | -6.1554 | - |
| SKIP_PAPER | 0.0 | 1.2732 | 0.6783 | -0.366 | - |

### ABBV → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.7044 | 1.2409999999999997 | HIGH_RISK_MITIGATED_BY_POSITIVE_EV |
| SKIP_PAPER | 0.0 | 0.0 | 0.6552 | -0.0 | - |

### AIR.PA → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.7841 | 2.4364999999999997 | APPE_HIGH_RISK_POLICY,APPE_CAPITAL_PRESERVATION |
| HOLD_PAPER | 0.0 | 3.0 | 0.7447 | -3.45 | - |
| PROTECT_PAPER | 0.0 | 12.75 | 0.7614 | -14.6625 | - |
| REDUCE_PAPER | 0.0 | 10.2 | 0.6947 | -11.73 | - |
| ROTATE_PAPER | 0.0 | 6.6 | 0.6947 | -7.59 | - |
| SELL_PAPER | 0.0 | 0.0 | 0.6947 | 0.0 | - |
| SKIP_PAPER | 0.0 | 0.0 | 0.6614 | -0.0 | - |

### ALV.DE → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.7291 | 1.6115000000000004 | HIGH_RISK_MITIGATED_BY_POSITIVE_EV |
| SKIP_PAPER | 0.0 | 0.0 | 0.684 | -0.0 | - |

### AMAT → SELL_PAPER (HARD_RULE)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| SELL_PAPER | 22.25 | 17.0 | 0.716 | -3.6183 | - |

### AZN.L → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.7098 | 1.322 | HIGH_RISK_MITIGATED_BY_POSITIVE_EV |
| SKIP_PAPER | 0.0 | 0.0735 | 0.6614 | -0.0211 | - |

### BP.L → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.7383 | 1.7495000000000003 | HIGH_RISK_MITIGATED_BY_POSITIVE_EV |
| SKIP_PAPER | 0.0 | 0.0 | 0.6614 | -0.0 | - |

### DIA → BUY_PAPER (EV_OPTIMIZER)

| action | profit Δ | drawdown | P(success) | raEV | blockers |
| --- | --- | --- | --- | --- | --- |
| BUY_PAPER | 15.0 | 5.5 | 0.7841 | 2.4364999999999997 | APPE_HIGH_RISK_POLICY,APPE_CAPITAL_PRESERVATION |
| HOLD_PAPER | 0.0 | 3.0 | 0.7447 | -3.45 | - |
| PROTECT_PAPER | 0.0 | 12.75 | 0.7614 | -14.6625 | - |
| REDUCE_PAPER | 0.0 | 10.2 | 0.6947 | -11.73 | - |
| ROTATE_PAPER | 0.0 | 6.6 | 0.6947 | -7.59 | - |
| SELL_PAPER | 0.0 | 0.0 | 0.6947 | 0.0 | - |
| SKIP_PAPER | 0.0 | 0.0 | 0.6614 | -0.0 | - |

## Safety

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| NO_BROKER | ✅ |
| live_promotion_allowed | **false** |
| Overrides hard rules | **false** |
