# TAE Full Ecosystem Review

**Generated:** 2026-06-29T23:46:29.796464+00:00  
**Mode:** OBSERVABILITY_FINANCIAL_ANALYSIS  
**Live trading impact:** NONE

## A. Runtime Status
- Bot effective: **STOPPED**
- Bot process: STOPPED
- Dashboard process: RUNNING
- Status file: STOPPED
- Bot log age (s): 11243.8
- Live signals age (s): 11244.3
- Health: TAE_QUICK_HEALTH_READY_WITH_WARNINGS
- Advisory: SELL_ADVISORY (blocks new BUY: False)
- Git clean: False

## Market Readiness
- Local time: 2026-06-30T02:46:29.748559+03:00
- Verdict: **READY**
- Session guard reason: all_markets_closed
- Bot stopped expected: True
- Markets: {'US': False, 'EU': False, 'UK': False, 'ASIA': False}
- Dashboard running: True
- X.8 blocks new BUY: False
- Advisory blocking warnings: 0 | informational: 5
- RISK from real blockers only: False
- SELL accounting protection: ACTIVE
- X.9 ledger: READY
- BUY path will log on open: True
- Next action: WAIT_FOR_MARKET_OPEN_THEN_SESSION_GUARD_START

## B. Financial Status (estimated, trading-only PnL)
- Cash: 19954.03 USD
- Capital deposits (flows): 0.0 USD
- Open positions: 5
- Portfolio value (est.): 30395.47 USD
- Trading realized PnL: -700.3663
- Trading unrealized PnL: 127.7219
- **Corrected trading total PnL:** 395.4641
- Raw total PnL (incl. CASH rows): -10918.8484
- Accounting adjustments excluded: -9913.58
- Daily trading PnL: None
- Profit % (on 30000.0 baseline): 1.3182%
- Execution integrity: MISMATCH_DETECTED (SELL mismatches: 26)
- Corrected realized PnL: 267.7422

## Performance Drag Analysis
- Stop-loss total: None (None trades)
- Take-profit total: None (None trades)
- Recommended next fix: PORTFOLIO_ACCOUNTING_MIGRATION
- Top losing trades:
  - AAPL: -189.2578 (STOP LOSS -8.24%)
  - ORCL: -105.4381 (STOP LOSS -11.64%)
  - SIE.DE: -93.6152 (STOP LOSS -3.02%)
- CASH distortion: CASH/DEPOSIT row reported PnL -9913.58 distorts raw portfolio sums; excluded from corrected trading PnL.

## C. Live Signals Today
- Total: 15 | STRONG BUY: 5 | TAKE PROFIT: 4 | WAIT: 6

## D. TAE Advisory
- Action: **SELL_ADVISORY** | Confidence: 78
- SELL_ADVISORY: review exits only; no auto-sell.

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
- TAKE_PROFIT_REVIEW
- CONSIDER_TOP_STRATEGY_ALIGNMENT

## J. Final Verdict
- **ECOSYSTEM_HEALTHY**
- Financial today: UNKNOWN
- Learning progress: STATIC
- Next action: WAIT_FOR_MARKET_OPEN_THEN_SESSION_GUARD_START

## Cannot Conclude Yet
- Gate performance: no shadow validation events yet.
- Counterfactual top_100/top_200: not enough robust strategies in artifacts.
- Daily PnL: no portfolio activity dated today.
- Live intraday behavior: bot STOPPED limits same-day observations.
- Forward PnL on blocked BUYs: outcome_tracking_status PENDING_NEXT_PHASE.

