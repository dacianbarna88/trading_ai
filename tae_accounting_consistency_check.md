# TAE Accounting Consistency Check

**Verdict:** **PASS**
**Generated:** 2026-06-29T23:05:36.430878+00:00

## Canonical metrics

- account_value_corrected: 40395.46
- corrected_total_trading_pnl: 395.4641
- corrected_realized_pnl: 267.7422
- corrected_unrealized_pnl: 127.7219
- capital_deposits: 10000.0
- cash_available: 29954.03
- data_quality_status: HISTORICAL_RECONCILIATION_REQUIRED
- top_drag_corrected: {'date': '2026-06-25 18:19:50', 'ticker': 'AAPL', 'pnl': -189.2578, 'pnl_pct': -7.5703, 'reported_pnl': 40.3048, 'reason': 'STOP LOSS -8.24%', 'signal': 'WAIT', 'consistency_status': 'MISMATCH_REASON_PNL'}

## Checks

- [PASS] **review_corrected_pnl_matches_snapshot** — review=395.4641 snapshot=395.4641
- [PASS] **review_realized_matches_snapshot** — review=267.7422 snapshot=267.7422
- [PASS] **account_value_formula** — account_value=40395.46 expected=40395.46
- [PASS] **gs_not_negative_top_drag** — GS in top losers with stale negative=False corrected GS pnl=547.9904
- [PASS] **snapshot_file_present** — snapshot file status=OK
- [PASS] **data_quality_documented** — status=HISTORICAL_RECONCILIATION_REQUIRED
