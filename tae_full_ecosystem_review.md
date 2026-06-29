# TAE Full Ecosystem Review

**Generated:** 2026-06-29T22:10:41.395352+00:00  
**Mode:** OBSERVABILITY_FINANCIAL_ANALYSIS  
**Live trading impact:** NONE

## A. Runtime Status
- Bot effective: **STOPPED**
- Bot process: STOPPED
- Dashboard process: STOPPED
- Status file: STOPPED
- Bot log age (s): 5495.4
- Live signals age (s): 5495.9
- Health: TAE_QUICK_HEALTH_READY_WITH_WARNINGS
- Advisory: RISK_ADVISORY (blocks new BUY: True)
- Git clean: False

## Market Readiness
- Local time: 2026-06-30T01:10:41.346429+03:00
- Verdict: **READY**
- Session guard reason: all_markets_closed
- Bot stopped expected: True
- Markets: {'US': False, 'EU': False, 'UK': False, 'ASIA': False}
- Dashboard running: False
- X.8 blocks new BUY: True
- X.9 ledger: NO_EVENTS_YET
- BUY path will log on open: True
- Next action: WAIT_FOR_MARKET_OPEN_THEN_SESSION_GUARD_START

## B. Financial Status (estimated)
- Cash: 29954.03 USD
- Open positions: 5
- Portfolio value (est.): 40395.46 USD
- Realized PnL: -700.3663
- Unrealized PnL: 127.7219
- Daily PnL: None
- Total PnL: -572.6444 (-1.9088%)

## C. Live Signals Today
- Total: 15 | STRONG BUY: 5 | TAKE PROFIT: 4 | WAIT: 6

## D. TAE Advisory
- Action: **RISK_ADVISORY** | Confidence: 53
- RISK_ADVISORY active: new BUY orders would be blocked by X.8 gate in live_bot.
- 5 STRONG BUY signal(s) present — TAE would block new entries today.

## E. X.9 Shadow Validation
- Events: 0 | Allowed: 0 | Blocked: 0 | Skipped: 0
- Block rate: 0.0
- tae_shadow_validation_events.csv missing — X.9 ledger connected in live_bot but no events recorded yet; cannot evaluate gate performance.

## F. Strategy Universe
- Unique strategy IDs: 64
- Robust shortlist: 25
- Weak shortlist: 25
- Registry candidates: 3
- Median robust profit_pct: 227.7536
- Median robust Sharpe: 0.9966

## G. Counterfactual (robust shortlist, median-first)
- top_1: used 1/1 | median profit_pct=-44.7875 | median Sharpe=3.7132 | status=OK
- top_5: used 5/5 | median profit_pct=21.7982 | median Sharpe=1.6392 | status=OK
- top_10: used 10/10 | median profit_pct=21.2615 | median Sharpe=1.4156 | status=OK
- top_100: used 25/100 | median profit_pct=227.7536 | median Sharpe=0.9966 | status=INSUFFICIENT_DATA
- top_200: used 25/200 | median profit_pct=227.7536 | median Sharpe=0.9966 | status=INSUFFICIENT_DATA

## H. Learning / Evidence / Meta
- Evidence verdict: EVIDENCE_ENGINE_SOURCE_OF_TRUTH_ALIGNED
- Meta confidence: {'composite_score': 0.9889, 'confidence_label': 'HIGH', 'factors': {'runtime_health': 1.0, 'orchestrator': 1.0, 'strategy_evolution': 1.0, 'governance': 1.0, 'top_strategy_score': 0.9336, 'input_coverage': 1.0}}
- Ranking count: 3
- Artifacts generated today: []

## I. Profit Maximization Advisory (no auto execution)
- COLLECT_MORE_DATA
- DO_NOT_BUY
- TAKE_PROFIT_REVIEW
- CONSIDER_TOP_STRATEGY_ALIGNMENT

## J. Final Verdict
- **WARNING**
- Financial today: UNKNOWN
- Learning progress: STATIC
- Next action: DO_NOT_OPEN_NEW_BUY_REVIEW_EXISTING

## Cannot Conclude Yet
- Gate performance: no shadow validation events yet.
- Counterfactual top_100/top_200: not enough robust strategies in artifacts.
- Daily PnL: no portfolio activity dated today.
- Live intraday behavior: bot STOPPED limits same-day observations.
- Forward PnL on blocked BUYs: outcome_tracking_status PENDING_NEXT_PHASE.

