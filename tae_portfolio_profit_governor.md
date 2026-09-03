# TAE Portfolio Profit Governor v1

**Generated:** 2026-09-03T16:01:33
**Mode:** SHADOW_ONLY — NONE
**Portfolio verdict:** PORTFOLIO_WATCH
**Final status:** PPG_SHADOW_READY_FOR_OBSERVATION

> **NO BUY / NO SELL — SHADOW_ONLY portfolio profit VIEW**

Portfolio-level profit VIEW — no live orders; execution remains live_bot.py

## Safety mode

- SHADOW_ONLY: **true**
- NO_BROKER: **true**
- NO_LIVE_EXECUTION_CHANGE: **true**
- portfolio.csv modified: **false**

## Portfolio metrics

- Total positions: **22**
- Profitable: **0**
- Losing: **0**
- Keep winner: **0**
- Protect shadow: **0**
- Trail shadow: **0**
- Watch shadow: **8**
- Observe shadow: **14**
- Aggregate missed USD: **0**
- Profit quality score: **31.5**
- Profit at risk score: **15.7**
- Concentration risk score: **30.2**

## Regional risk summary

| region | positions |
| --- | --- |
| US | 15 |
| EU | 5 |
| UK | 4 |
| OTHER | 0 |

## Sector risk summary

- Leader: **TECHNOLOGY (XLK)**
- Score: **24.52**
- View: **UNDERWEIGHT_COMMUNICATIONS**
- Summary: **LEADER_TECHNOLOGY**

## Top 5 risky tickers

| ticker | governor score | posture | final rec | protect score |
| --- | --- | --- | --- | --- |
| MU | 48.6 | WATCH_SHADOW | WATCH | 67.0 |
| QQQ | 49.9 | WATCH_SHADOW | WATCH | 47.0 |
| HSBA.L | 52.1 | WATCH_SHADOW | WATCH | 67.0 |
| AMAT | 52.2 | OBSERVE_SHADOW | OBSERVE | 52.0 |
| AIR.PA | 52.2 | WATCH_SHADOW | WATCH | 47.0 |

## Top 5 keep winners

| ticker | governor score | context score | PCE verdict |
| --- | --- | --- | --- |

## Sources loaded

- ✅ portfolio.csv
- ✅ runtime_outputs/sector_intelligence_summary.txt
- ✅ tae_profit_committee_learning.json
- ✅ tae_profit_context_engine.json
- ✅ tae_profit_decision_governor.json
- ✅ tae_profit_intelligence_brain.json
- ✅ tae_profit_memory_engine.json
- ❌ tae_profit_protection_shadow.json
- ❌ tae_profit_protection_validation.json

## Explanation

SHADOW_ONLY portfolio governor: 22 positions, verdict=PORTFOLIO_WATCH. Postures — keep=0, protect=0, trail=0, watch=8. Scores — quality=31.5, at_risk=15.7, concentration=30.2. Aggregate missed USD=0.00. Regional mix: US=15, EU=5, UK=4, OTHER=0. Sector context: LEADER_TECHNOLOGY. NO BUY / NO SELL — observation VIEW only.

