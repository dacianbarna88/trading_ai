# TAE Portfolio Profit Governor v1

**Generated:** 2026-07-06T19:01:49
**Mode:** SHADOW_ONLY — NONE
**Portfolio verdict:** PORTFOLIO_HIGH_RISK
**Final status:** PPG_SHADOW_READY_FOR_OBSERVATION

> **NO BUY / NO SELL — SHADOW_ONLY portfolio profit VIEW**

Portfolio-level profit VIEW — no live orders; execution remains live_bot.py

## Safety mode

- SHADOW_ONLY: **true**
- NO_BROKER: **true**
- NO_LIVE_EXECUTION_CHANGE: **true**
- portfolio.csv modified: **false**

## Portfolio metrics

- Total positions: **12**
- Profitable: **8**
- Losing: **4**
- Keep winner: **4**
- Protect shadow: **2**
- Trail shadow: **2**
- Watch shadow: **3**
- Observe shadow: **1**
- Aggregate missed USD: **829.72**
- Profit quality score: **55.6**
- Profit at risk score: **33.6**
- Concentration risk score: **66.6**

## Regional risk summary

| region | positions |
| --- | --- |
| US | 9 |
| EU | 2 |
| UK | 1 |
| OTHER | 0 |

## Sector risk summary

- Leader: **TECHNOLOGY (XLK)**
- Score: **24.52**
- View: **UNDERWEIGHT_COMMUNICATIONS**
- Summary: **LEADER_TECHNOLOGY**

## Top 5 risky tickers

| ticker | governor score | posture | final rec | protect score |
| --- | --- | --- | --- | --- |
| HSBA.L | 24.9 | TRAIL_SHADOW | TRAIL_PROTECT_SHADOW | 100.0 |
| AMAT | 24.9 | PROTECT_SHADOW | PARTIAL_PROTECT_SHADOW | 100.0 |
| MU | 24.9 | PROTECT_SHADOW | PARTIAL_PROTECT_SHADOW | 100.0 |
| LLY | 31.8 | TRAIL_SHADOW | TRAIL_PROTECT_SHADOW | 100.0 |
| QQQ | 46.9 | WATCH_SHADOW | WATCH | 62.0 |

## Top 5 keep winners

| ticker | governor score | context score | PCE verdict |
| --- | --- | --- | --- |
| MRK | 94.9 | 89.8 | KEEP_WINNER |
| PM | 91.2 | 82.4 | KEEP_WINNER |
| SPY | 89.5 | 79.1 | KEEP_WINNER |
| PG | 82.7 | 82.4 | KEEP_WINNER |

## Sources loaded

- ✅ portfolio.csv
- ✅ runtime_outputs/sector_intelligence_summary.txt
- ✅ tae_profit_committee_learning.json
- ✅ tae_profit_context_engine.json
- ✅ tae_profit_decision_governor.json
- ✅ tae_profit_intelligence_brain.json
- ✅ tae_profit_memory_engine.json
- ✅ tae_profit_protection_shadow.json
- ✅ tae_profit_protection_validation.json

## Explanation

SHADOW_ONLY portfolio governor: 12 positions, verdict=PORTFOLIO_HIGH_RISK. Postures — keep=4, protect=2, trail=2, watch=3. Scores — quality=55.6, at_risk=33.6, concentration=66.6. Aggregate missed USD=829.72. Regional mix: US=9, EU=2, UK=1, OTHER=0. Sector context: LEADER_TECHNOLOGY. NO BUY / NO SELL — observation VIEW only.

