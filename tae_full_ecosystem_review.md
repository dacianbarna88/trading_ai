# TAE Full Ecosystem Review

**Generated:** 2026-06-30T12:30:31.097883+00:00  
**Mode:** OBSERVABILITY_FINANCIAL_ANALYSIS  
**Live trading impact:** NONE

## A. Runtime Status
- Bot effective: **RUNNING**
- Bot process: STOPPED
- Dashboard process: RUNNING
- Status file: RUNNING
- Bot log age (s): 0.2
- Live signals age (s): 31.0
- Health: TAE_QUICK_HEALTH_READY
- Advisory: SELL_ADVISORY (blocks new BUY: False)
- Git clean: False

## Market Readiness
- Local time: 2026-06-30T15:30:31.051794+03:00
- Verdict: **READY**
- Session guard reason: market_session_open
- Bot stopped expected: False
- Markets: {'US': False, 'EU': True, 'UK': True, 'ASIA': False}
- Dashboard running: True
- X.8 blocks new BUY: False
- Advisory blocking warnings: 0 | informational: 6
- RISK from real blockers only: False
- SELL accounting protection: ACTIVE
- X.9 ledger: READY
- BUY path will log on open: True
- Next action: MARKET_OPEN_MONITOR_SIGNALS_AND_LEDGER

## B. Financial Status (estimated, trading-only PnL)
- Cash: 22662.33 USD
- Capital deposits (flows): 0.0 USD
- Open positions: 4
- Portfolio value (est.): 30453.41 USD
- Trading realized PnL: -534.3556
- Trading unrealized PnL: -21.7882
- **Corrected trading total PnL:** 453.4037
- Raw total PnL (incl. CASH rows): -10651.7041
- Accounting adjustments excluded: -9913.58
- Daily trading PnL: None
- Profit % (on 30000.0 baseline): 1.5113%
- Execution integrity: MISMATCH_DETECTED (SELL mismatches: 27)
- Corrected realized PnL: 475.1919

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
- Total: 25 | STRONG BUY: 8 | TAKE PROFIT: 9 | WAIT: 8

## D. TAE Advisory
- Action: **SELL_ADVISORY** | Confidence: 78
- SELL_ADVISORY: review exits only; no auto-sell.

## E. X.9 Shadow Validation
- Events: 461 | Allowed: 1 | Blocked: 0 | Skipped: 460
- Block rate: 0.0

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
- Meta confidence: {'composite_score': 0.9886, 'confidence_label': 'HIGH', 'factors': {'runtime_health': 1.0, 'orchestrator': 1.0, 'strategy_evolution': 1.0, 'governance': 1.0, 'top_strategy_score': 0.9315, 'input_coverage': 1.0}}
- Ranking count: 3
- Artifacts generated today: ['tae_live_advisory.json', 'tae_shadow_validation_summary.json', 'tae_advisory_index.json', 'tae_historical_execution.json', 'tae_historical_results_analysis.json', 'tae_continuous_strategy_ranking.json', 'tae_candidate_strategy_registry.json', 'tae_meta_intelligence.json', 'tae_quick_health_check.json']

## I. Profit Maximization Advisory (no auto execution)
- TAKE_PROFIT_REVIEW
- CONSIDER_TOP_STRATEGY_ALIGNMENT

## J. Final Verdict
- **ECOSYSTEM_HEALTHY**
- Financial today: UNKNOWN
- Learning progress: ACTIVE_TODAY
- Next action: REVIEW_TAE_ARTIFACTS

## Cannot Conclude Yet
- Counterfactual top_100/top_200: not enough robust strategies in artifacts.
- Daily PnL: no portfolio activity dated today.
- Forward PnL on blocked BUYs: outcome_tracking_status PENDING_NEXT_PHASE.

