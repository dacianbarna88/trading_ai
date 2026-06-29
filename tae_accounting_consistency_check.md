# TAE Accounting Consistency Check

**Verdict:** **PASS**
**Generated:** 2026-06-29T23:14:47.315433+00:00

## Canonical metrics

- starting_capital_config: 30000.0
- effective_contributed_capital: 30000.0
- capital_deposits_detected: 10000.0
- capital_deposits_counted: 0.0
- capital_deposits_excluded: 10000.0
- account_value_corrected: 30395.47
- account_value_cash_based: 30395.47
- account_value_capital_based: 30395.46
- corrected_total_trading_pnl: 395.4641
- corrected_realized_pnl: 267.7422
- corrected_unrealized_pnl: 127.7219
- cash_available: 19954.03
- open_positions_value: 10441.4351
- capital_base_status: NEEDS_OPERATOR_CONFIRMATION
- data_quality_status: HISTORICAL_RECONCILIATION_REQUIRED
- top_drag_corrected: {'date': '2026-06-25 18:19:50', 'ticker': 'AAPL', 'pnl': -189.2578, 'pnl_pct': -7.5703, 'reported_pnl': 40.3048, 'reason': 'STOP LOSS -8.24%', 'signal': 'WAIT', 'consistency_status': 'MISMATCH_REASON_PNL'}

## Checks

- [PASS] **review_corrected_pnl_matches_snapshot** — review=395.4641 snapshot=395.4641
- [PASS] **review_realized_matches_snapshot** — review=267.7422 snapshot=267.7422
- [PASS] **cash_plus_open_equals_account_value** — cash(19954.03)+open(10441.4351)=30395.47 vs account_value=30395.47
- [PASS] **effective_capital_plus_pnl_equals_account_value** — effective(30000.0)+pnl(395.4641)=30395.46 vs account_value=30395.46
- [PASS] **account_value_dual_path_reconciles** — cash_based=30395.47 capital_based=30395.46 delta=0.01
- [PASS] **virtual_deposit_not_double_counted** — detected=10000.0 excluded=10000.0 counted=0.0 — virtual $10000.0 excluded from effective capital; account value does NOT add deposit on top of $30k base
- [PASS] **capital_base_status_documented** — status=NEEDS_OPERATOR_CONFIRMATION
- [PASS] **gs_not_negative_top_drag** — GS in top losers with stale negative=False corrected GS pnl=547.9904
- [PASS] **snapshot_file_present** — snapshot file status=OK
- [PASS] **data_quality_documented** — status=HISTORICAL_RECONCILIATION_REQUIRED
