# Trading AI Project Status

## TAE Ecosystem — Official Stable (Phase IX)

| Field | Value |
|-------|-------|
| **Current TAE stable** | **TAE V9.6 Stable** |
| **Sprint** | IX.6 — Official Stable Release |
| **Checkpoint commit** | `b2bbd1e` |
| **Archive** | `archive/v9_6_stable/` |
| **Runtime health** | HEALTHY |
| **Integration backlog** | NONE |
| **Official quick health** | `python3 tae_quick_health_check.py` |
| **TAE status doc** | `TAE_PROJECT_STATUS.md` |

Operating mode: `ANALYSIS_ONLY` | `PAPER_ONLY` | `NO_BROKER` | `NO_EXECUTION`

---

## Live Trading Stack — Current Stable Version

## Current Stable Version

V14.5 Threshold Virtual Tracker

## Latest Stable Snapshots

archive/v12_7_1_position_intelligence_auto_refresh_stable
archive/v13_4_0_rebalance_edge_engine_stable
archive/v14_3_0_learning_recommendations_stable
archive/v14_5_0_threshold_virtual_tracker_stable
archive/v9_6_stable

## Active Core Systems

✅ Live Bot
✅ Market Regime Engine
✅ Risk Guardian
✅ Position Intelligence
✅ Post-Sell Audit Engine
✅ Missed Winners Audit Engine
✅ Rebalance Edge Engine
✅ Learning Engine
✅ Learning Insights
✅ Learning Scoreboard
✅ Learning Recommendations
✅ Threshold Test Simulator
✅ Threshold Virtual Tracker

## Current Open Positions

V
BRK-B
CSCO
HSBA.L
SIE.DE

## Current Learning Metrics

Sell Quality: 84.21%
Rebalance Edge: 0.00%
Missed Winner Rate: 27.78%
Threshold Opportunity: +6

## Learning Recommendations

SELL_ENGINE_OK
REBALANCE_INCONCLUSIVE
WATCH_THRESHOLD_80
THRESHOLD_TEST_RECOMMENDED

## Threshold Tracking

Real Buy Threshold: 90

Virtual Threshold Under Evaluation: 80

Tracked Virtual Positions:

AIR.PA
NVDA
ULVR.L
SPY

## Latest Fixes

V12.7.1 Position Intelligence Auto Refresh

Verified:
Position Intelligence actualizat automat după update_portfolio_prices()

## Project Flags

PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION

## Next Development Target

V14.6 Threshold Outcome Auditor

Goal:

Evaluate whether virtual threshold-80 candidates outperform the current threshold-90 approach using real market outcomes.


---

## TAE Sprint X.7–X.9 Checkpoint

> **Canonical journal:** see `PROJECT_BOOK.md` and `SESSION_START.md`. This section is a short runtime pointer only.

### Latest
- **X.9 COMPLETED** — Connected Shadow Validation Ledger (`shadow_validation_ledger.py`, `tae_shadow_validation_report.py`, BUY path in `live_bot.py`)
- **Next:** X.10 Outcome Tracking — only after `tae_shadow_validation_events.csv` accumulates events

### Status Git (pre-X.9 commit)
- X.7–X.8: committed & pushed
- X.9 implementation: pending commit (`live_bot.py`, ledger, report, `TAE_X9_SHADOW_VALIDATION_SUMMARY.md`)

### Ce avem acum (TAE → LIVE)

- X.8: `RISK_ADVISORY` blochează doar BUY noi; SELL neatins
- X.9: observability BUY (`BUY_ALLOWED` / `BUY_BLOCKED_BY_TAE` / `BUY_SKIPPED_OTHER_REASON`); SELL neatins
- Outcome tracking: **PENDING_NEXT_PHASE**

### Ce NU avem încă

- Forward PnL / attribution pe BUY-uri blocate (X.10)
- TAE sizing / scoring / trailing / settings changes
- Event memory ingestion

### Următorul pas recomandat

**TAE Sprint X.10** — Outcome Tracking / Attribution for blocked BUYs (după acumulare evenimente în ledger).

