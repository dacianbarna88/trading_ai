# Cleanup Manifest Update Summary

**Source:** `cleanup_dependency_audit.md`  
**Action:** Updated `Action` column only in `cleanup_before_github_manifest.csv`  
**No files were moved or deleted.**

## Counts

| Action | Before | After | Delta |
|--------|--------|-------|-------|
| KEEP | 115 | 218 | +103 |
| MOVE_TO_CLEANUP_ARCHIVE | 154 | 51 | -103 |
| REVIEW_MANUAL | 157 | 157 | +0 |

## Transitions from `MOVE_TO_CLEANUP_ARCHIVE`

| Transition | Count | Notes |
|------------|-------|-------|
| → `KEEP` | **103** | Runtime-referenced per dependency audit |
| → `MOVE_TO_CLEANUP_ARCHIVE` (retained) | **51** | No runtime references (includes `main.py` false positive and `v42_engine.py`) |
| → `REVIEW_MANUAL` | **0** | |

### Audit alignment

- Dependency audit listed **105** incorrectly-marked paths; **`main.py`** is a scanner false positive (import alias, not root file) → retained as `MOVE_TO_CLEANUP_ARCHIVE`.
- **`v42_engine.py`** is only referenced by legacy `autopilot.py` (also slated for quarantine) → retained as `MOVE_TO_CLEANUP_ARCHIVE`.
- Effective runtime `KEEP` promotions: **103** (105 − `main.py` − `v42_engine.py`).

## Final `MOVE_TO_CLEANUP_ARCHIVE` files (51)

- `Trading AI Dashboard.pdf`
- `V28_0_CHECKPOINT_STATUS.txt`
- `V29_0_STABLE_STATUS.txt`
- `V30_0_PROJECT_STATUS.txt`
- `V31_0_PROJECT_STATUS.txt`
- `V32_0_PROJECT_STATUS.txt`
- `advanced_backtest.py`
- `autopilot.py`
- `backtest.py`
- `bot.py`
- `bot_error_old.log`
- `bot_output_before_extra_cash_test.log`
- `committee_learning_engine_before_v9_6.py`
- `confidence_intelligence/weighted_committee_engine_before_v28_1.py`
- `crontab_backup_before_market_session_guard_20260624_094710.txt`
- `crontab_backup_before_runner_fix.txt`
- `full_autopilot.py`
- `main.py`
- `market_autopilot_final.py`
- `market_open_runner_before_awake_guard_fix.sh`
- `market_open_runner_before_v37_7_fix.sh`
- `outcome_evaluator_test.py`
- `portfolio_before_extra_cash_test.csv`
- `portfolio_before_v12_4_integrity_fix.csv`
- `portfolio_before_v36_6_integrity_cleanup.csv`
- `portfolio_before_v37_4_brkb_sell_correction.csv`
- `portfolio_before_v37_5_trailing_field_cleanup.csv`
- `portfolio_before_v38_1_buy_current_value_fix.csv`
- `project_cleanup_audit.py`
- `project_cleanup_audit_report.txt`
- `project_cleanup_delete_candidates_only.txt`
- `run_dashboard.py`
- `v37_4_buy_sell_logic_test.py`
- `v37_5_trailing_logic_test.py`
- `v37_6_open_positions_test.py`
- `v38_1_portfolio_reconciliation_audit.py`
- `v38_4_position_capacity_audit.py`
- `v38_5_position_quality_audit.py`
- `v38_6_slot_pressure_audit.py`
- `v39_0_selection_quality_audit.py`
- `v39_1_capacity_simulation.py`
- `v40_1_strategic_rank_engine.py`
- `v40_2_decision_simulation.py`
- `v40_5_backtest_v39_vs_v40.py`
- `v41_3_portfolio_impact.py`
- `v41_autopilot.py`
- `v41_fusion_engine.py`
- `v41_gate_patch.py`
- `v41_live_observer.py`
- `v42_engine.py`
- `watchlist_backup.txt`
