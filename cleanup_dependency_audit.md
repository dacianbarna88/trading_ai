# Cleanup Dependency Re-Audit

**Date:** 2026-06-24
**Scope:** Re-audit every `MOVE_TO_CLEANUP_ARCHIVE` row in `cleanup_before_github_manifest.csv`
**Method:** Static reference scan — imports, quoted paths, shell tokens — across the project (excluding `archive/`, cleanup meta-files).
**No files were moved or modified.**

## Summary

| Metric | Count |
|--------|-------|
| Original `MOVE_TO_CLEANUP_ARCHIVE` in manifest | 154 |
| **Should change to `KEEP`** (true runtime references) | **105** |
| **False positive** (`main.py` — import alias, not root file) | **1** |
| **Safe to quarantine** (no runtime references found) | **49** |
| Recommended post-audit `MOVE_TO_CLEANUP_ARCHIVE` | **49** |

### Scan sources (as requested)

- `live_bot.py`, `live_bot_v5_1.py`, `bot_controller.py`, `daily_intelligence_runner.py`
- `market_session_guard.sh`, `market_open_runner.sh`, `market_close_runner.sh`
- All `.py` files in `config/`, `core/`, `data/`, `engine/`, `intelligence/`, `research/`, `utils/`
- Plus transitive BFS through imports and file-path strings from those entry points
- Plus all other root `.py` / `.sh` files (excluding cleanup meta-artifacts)

### Excluded from reference corpus (meta only)

- `cleanup_before_github_manifest.csv`, `cleanup_before_github_plan.md`
- `project_cleanup_audit.py`, `project_cleanup_audit_report.txt`, `project_cleanup_delete_candidates_only.txt`

---

## Runtime dependencies discovered

### Scheduler / shell runners

| Runner | Invokes | MOVE file affected |
|--------|---------|-------------------|
| `market_open_runner.sh` | `awake_guard.sh`, `bot_controller.start_bot()`, `morning_update.py`, `daily_intelligence_runner.py` | `morning_update_report.txt` (output of `morning_update.py`) |
| `market_close_runner.sh` | `daily_intelligence_runner.py`, **`full_backup_runner.py`** | **`full_backup_runner.py`** + backup chain |
| `market_session_guard.py` | `awake_guard.sh` | (awake_guard is `REVIEW_MANUAL`, not MOVE) |

### Backup chain (market close)

```
market_close_runner.sh
  → full_backup_runner.py
    → cloud_backup_sync.py, external_backup_sync.py
    → full_backup_runner_report.txt
    → backup_engine.py → backup_engine_report.txt
```

### Live bot / signals chain (v5.1 path)

```
live_signal_refresh.py → live_bot_v5_1.py → research.signals.generate_signals
  → core.v41_shadow.run_v41_shadow
    → v41_4_live_strategy.py
      → v41_gate.py
```

`live_bot.py` (started by `bot_controller.py`) is a standalone script and does not import this v41 chain directly, but **`research/signals.py` is live code** in a protected directory and hard-wires the v41 shadow path.

### Morning update

```
market_open_runner.sh → morning_update.py → morning_update_report.txt
```

### Threshold intelligence (`intelligence/` + root engines)

```
intelligence/threshold_intelligence_layer.py reads:
  threshold_outcome_summary.txt, threshold_decision_summary.txt,
  threshold_confidence_summary.txt, threshold_history_summary.txt
  → writes threshold_intelligence_summary.txt

intelligence/threshold_decision_gate.py → threshold_outcome_summary.txt
intelligence/threshold_confidence_engine.py → threshold_outcome_report.csv
```

Root engines (`threshold_virtual_tracker.py`, `learning_engine.py`, `hard_risk_guardian.py`, etc.) read/write their own `*_summary.txt` outputs — not shown in `dashboard_v2.py` but required for pipeline regeneration.

### `research/` summary outputs

Multiple `research/*.py` modules write summaries flagged for MOVE, e.g.:

- `research/cross_market_regime.py` → `cross_market_regime_summary.txt`
- `research/regime_forecast.py` → `regime_forecast_summary.txt`
- `research/global_portfolio_manager.py` → `market_rotation_summary.txt`
- `research/allocation_signals.py` → `allocation_signals_summary.txt`
- `research/horizon_validation_engine.py` → `horizon_validation_summary.txt`

### `daily_intelligence_runner.py`

Runs engines directly (not MOVE targets themselves), but those engines depend on summary files now marked KEEP, e.g. `outcome_analytics_summary.txt` ← `master_intelligence_score.py`.

### False positive noted

- **`main.py`** (root): flagged via `live_bot_v5_1.py` importing `research.multi_market_scanner.main` (function name `main`, not root `main.py`). **Root `main.py` appears safe to quarantine.**

---

## Files incorrectly marked for move → should be `KEEP` (105 + 1 false positive)

Grouped by primary referrer category.

### Shell runners (1)

- `full_backup_runner.py`
  - `market_close_runner.sh` (token:full_backup_runner.py)

### Live bot / v41 chain (11)

- `conflict_position_sizing_summary.txt`
  - `conflict_position_sizing.py` (quoted:conflict_position_sizing_summary.txt)
  - `strategic_committee.py` (quoted:conflict_position_sizing_summary.txt)
  - `committee_confidence_engine.py` (quoted:conflict_position_sizing_summary.txt)
  - `backup_v41_pre_market/committee_confidence_engine.py` (quoted:conflict_position_sizing_summary.txt)
- `historical_memory_summary.txt`
  - `historical_memory_engine.py` (quoted:historical_memory_summary.txt)
  - `backup_v41_pre_market/historical_memory_engine.py` (quoted:historical_memory_summary.txt)
- `market_open_readiness_summary.txt`
  - `market_open_readiness.py` (quoted:market_open_readiness_summary.txt)
  - `backup_v41_pre_market/market_open_readiness.py` (quoted:market_open_readiness_summary.txt)
- `market_session_monitor_summary.txt`
  - `market_session_monitor.py` (quoted:market_session_monitor_summary.txt)
  - `backup_v41_pre_market/market_session_monitor.py` (quoted:market_session_monitor_summary.txt)
- `missed_winners_audit_report.csv`
  - `learning_engine.py` (quoted:missed_winners_audit_report.csv)
  - `missed_winners_audit.py` (quoted:missed_winners_audit_report.csv)
  - `backup_v41_pre_market/missed_winners_audit.py` (quoted:missed_winners_audit_report.csv)
- `missed_winners_audit_summary.txt`
  - `missed_winners_audit.py` (quoted:missed_winners_audit_summary.txt)
  - `backup_v41_pre_market/missed_winners_audit.py` (quoted:missed_winners_audit_summary.txt)
- `outcome_evolution_summary.txt`
  - `outcome_evolution_engine.py` (quoted:outcome_evolution_summary.txt)
  - `backup_v41_pre_market/outcome_evolution_engine.py` (quoted:outcome_evolution_summary.txt)
- `overnight_gap_risk_report.csv`
  - `overnight_gap_risk_guard.py` (quoted:overnight_gap_risk_report.csv)
  - `backup_v41_pre_market/overnight_gap_risk_guard.py` (quoted:overnight_gap_risk_report.csv)
- `overnight_gap_risk_summary.txt`
  - `overnight_gap_risk_guard.py` (quoted:overnight_gap_risk_summary.txt)
  - `backup_v41_pre_market/overnight_gap_risk_guard.py` (quoted:overnight_gap_risk_summary.txt)
- `v41_4_live_strategy.py`
  - `core/v41_shadow.py` (import:v41_4_live_strategy)
- `v41_gate.py`
  - `v41_4_live_strategy.py` (import:v41_gate)
  - `market_autopilot_final.py` (import:v41_gate)
  - `v41_autopilot.py` (import:v41_gate)
  - `v41_3_portfolio_impact.py` (import:v41_gate)
  - `full_autopilot.py` (import:v41_gate)
  - `v41_gate_patch.py` (import:v41_gate)
  - `v41_live_observer.py` (import:v41_gate)

### research/ (8)

- `allocation_signals_summary.txt`
  - `research/allocation_signals.py` (quoted:allocation_signals_summary.txt)
- `core_exposure_report.csv`
  - `research/portfolio_construction_engine.py` (quoted:core_exposure_report.csv)
  - `research/allocator_health_monitor.py` (quoted:core_exposure_report.csv)
  - `research/core_exposure_manager.py` (quoted:core_exposure_report.csv)
- `cross_market_regime_summary.txt`
  - `research/cross_market_regime.py` (quoted:cross_market_regime_summary.txt)
  - `research/strategic_committee.py` (quoted:cross_market_regime_summary.txt)
- `historical_intelligence_summary.txt`
  - `research/historical_intelligence_summary.py` (quoted:historical_intelligence_summary.txt)
  - `historical_intelligence_engine.py` (quoted:historical_intelligence_summary.txt)
  - `final_historical_intelligence_report.py` (quoted:historical_intelligence_summary.txt)
- `horizon_validation_summary.txt`
  - `research/horizon_validation_engine.py` (quoted:horizon_validation_summary.txt)
  - `strategic_intelligence/horizon_vote_engine.py` (quoted:horizon_validation_summary.txt)
- `market_rotation_summary.txt`
  - `research/global_portfolio_manager.py` (quoted:market_rotation_summary.txt)
  - `research/strategic_horizon.py` (quoted:market_rotation_summary.txt)
  - `research/global_opportunity_ranking.py` (quoted:market_rotation_summary.txt)
  - `research/market_rotation_summary.py` (quoted:market_rotation_summary.txt)
  - `research/strategic_committee.py` (quoted:market_rotation_summary.txt)
- `regime_forecast_summary.txt`
  - `research/regime_forecast.py` (quoted:regime_forecast_summary.txt)
  - `research/strategic_committee.py` (quoted:regime_forecast_summary.txt)
  - `regime_forecast_layer.py` (quoted:regime_forecast_summary.txt)
- `strategic_horizon_summary.txt`
  - `research/strategic_allocation_engine.py` (quoted:strategic_horizon_summary.txt)
  - `research/strategic_horizon.py` (quoted:strategic_horizon_summary.txt)
  - `research/strategic_portfolio_score.py` (quoted:strategic_horizon_summary.txt)
  - `research/strategic_committee.py` (quoted:strategic_horizon_summary.txt)
  - `strategic_intelligence/horizon_vote_engine.py` (quoted:strategic_horizon_summary.txt)

### intelligence/ (6)

- `threshold_confidence_summary.txt`
  - `intelligence/threshold_intelligence_layer.py` (quoted:threshold_confidence_summary.txt)
  - `intelligence/threshold_confidence_engine.py` (quoted:threshold_confidence_summary.txt)
- `threshold_decision_summary.txt`
  - `intelligence/threshold_decision_gate.py` (quoted:threshold_decision_summary.txt)
  - `intelligence/threshold_intelligence_layer.py` (quoted:threshold_decision_summary.txt)
- `threshold_history_summary.txt`
  - `intelligence/threshold_intelligence_layer.py` (quoted:threshold_history_summary.txt)
  - `intelligence/threshold_history_engine.py` (quoted:threshold_history_summary.txt)
- `threshold_intelligence_summary.txt`
  - `intelligence/threshold_intelligence_layer.py` (quoted:threshold_intelligence_summary.txt)
  - `strategic_intelligence/strategic_committee_engine.py` (quoted:threshold_intelligence_summary.txt)
  - `benchmark_intelligence/threshold_benchmark_engine.py` (quoted:threshold_intelligence_summary.txt)
- `threshold_outcome_report.csv`
  - `intelligence/threshold_confidence_engine.py` (quoted:threshold_outcome_report.csv)
  - `intelligence/threshold_history_engine.py` (quoted:threshold_outcome_report.csv)
  - `threshold_outcome_auditor.py` (quoted:threshold_outcome_report.csv)
- `threshold_outcome_summary.txt`
  - `intelligence/threshold_decision_gate.py` (quoted:threshold_outcome_summary.txt)
  - `intelligence/threshold_intelligence_layer.py` (quoted:threshold_outcome_summary.txt)
  - `threshold_outcome_auditor.py` (quoted:threshold_outcome_summary.txt)

### confidence_intelligence/ (12)

- `automatic_outcome_assignment_summary.txt`
  - `confidence_intelligence/automatic_outcome_assignment_engine.py` (quoted:automatic_outcome_assignment_summary.txt)
- `automatic_outcome_evaluator_summary.txt`
  - `confidence_intelligence/outcome_validation_summary_layer.py` (quoted:automatic_outcome_evaluator_summary.txt)
  - `confidence_intelligence/automatic_outcome_evaluator.py` (quoted:automatic_outcome_evaluator_summary.txt)
- `automatic_outcome_validation_summary.txt`
  - `confidence_intelligence/automatic_outcome_validation_engine.py` (quoted:automatic_outcome_validation_summary.txt)
- `benchmark_readiness_guard_summary.txt`
  - `confidence_intelligence/automatic_outcome_validation_engine.py` (quoted:benchmark_readiness_guard_summary.txt)
  - `benchmark_intelligence/benchmark_readiness_guard.py` (quoted:benchmark_readiness_guard_summary.txt)
  - `benchmark_intelligence/benchmark_execution_protected_summary.py` (quoted:benchmark_readiness_guard_summary.txt)
- `learning_weight_history_summary.txt`
  - `confidence_intelligence/learning_weight_history.py` (quoted:learning_weight_history_summary.txt)
- `outcome_scoring_summary.txt`
  - `confidence_intelligence/outcome_scoring_engine.py` (quoted:outcome_scoring_summary.txt)
- `registry_sync_summary.txt`
  - `confidence_intelligence/registry_sync_engine.py` (quoted:registry_sync_summary.txt)
- `validation_horizon_summary.txt`
  - `confidence_intelligence/outcome_validation_summary_layer.py` (quoted:validation_horizon_summary.txt)
  - `confidence_intelligence/validation_horizon_engine.py` (quoted:validation_horizon_summary.txt)
- `validation_rules_summary.txt`
  - `confidence_intelligence/validation_rules_engine.py` (quoted:validation_rules_summary.txt)
- `vote_accuracy_summary.txt`
  - `confidence_intelligence/confidence_evolution_summary.py` (quoted:vote_accuracy_summary.txt)
  - `confidence_intelligence/vote_accuracy_engine.py` (quoted:vote_accuracy_summary.txt)
- `vote_outcome_registry_summary.txt`
  - `confidence_intelligence/vote_outcome_registry.py` (quoted:vote_outcome_registry_summary.txt)
- `vote_outcome_summary.txt`
  - `confidence_intelligence/outcome_validation_summary_layer.py` (quoted:vote_outcome_summary.txt)
  - `confidence_intelligence/vote_outcome_validator.py` (quoted:vote_outcome_summary.txt)

### benchmark stack (13)

- `benchmark_data_quality_summary.txt`
  - `benchmark_data/benchmark_data_summary_layer.py` (quoted:benchmark_data_quality_summary.txt)
  - `benchmark_data/benchmark_data_layer_summary.py` (quoted:benchmark_data_quality_summary.txt)
  - `benchmark_data/benchmark_data_quality_guard.py` (quoted:benchmark_data_quality_summary.txt)
- `benchmark_data_summary.txt`
  - `benchmark_data/benchmark_data_summary_layer.py` (quoted:benchmark_data_summary.txt)
  - `benchmark_data/benchmark_data_layer_summary.py` (quoted:benchmark_data_summary.txt)
- `benchmark_execution_layer_summary.txt`
  - `benchmark_intelligence/benchmark_execution_summary_layer.py` (quoted:benchmark_execution_layer_summary.txt)
- `benchmark_execution_summary.txt`
  - `benchmark_intelligence/benchmark_execution_summary_layer.py` (quoted:benchmark_execution_summary.txt)
  - `benchmark_intelligence/benchmark_execution_protected_summary.py` (quoted:benchmark_execution_summary.txt)
  - `benchmark_intelligence/benchmark_execution_engine.py` (quoted:benchmark_execution_summary.txt)
- `benchmark_intelligence_summary.txt`
  - `benchmark_intelligence/benchmark_summary_layer.py` (quoted:benchmark_intelligence_summary.txt)
  - `benchmark_intelligence/benchmark_execution_summary_layer.py` (quoted:benchmark_intelligence_summary.txt)
- `benchmark_vote_mapper_summary.txt`
  - `benchmark_intelligence/benchmark_vote_mapper.py` (quoted:benchmark_vote_mapper_summary.txt)
  - `benchmark_intelligence/benchmark_execution_summary_layer.py` (quoted:benchmark_vote_mapper_summary.txt)
  - `benchmark_intelligence/benchmark_execution_protected_summary.py` (quoted:benchmark_vote_mapper_summary.txt)
- `horizon_benchmark_summary.txt`
  - `benchmark_intelligence/benchmark_summary_layer.py` (quoted:horizon_benchmark_summary.txt)
  - `benchmark_intelligence/horizon_benchmark_engine.py` (quoted:horizon_benchmark_summary.txt)
- `horizon_vote_summary.txt`
  - `strategic_intelligence/strategic_committee_engine.py` (quoted:horizon_vote_summary.txt)
  - `strategic_intelligence/horizon_vote_engine.py` (quoted:horizon_vote_summary.txt)
  - `benchmark_intelligence/horizon_benchmark_engine.py` (quoted:horizon_vote_summary.txt)
- `macro_benchmark_summary.txt`
  - `benchmark_intelligence/macro_benchmark_engine.py` (quoted:macro_benchmark_summary.txt)
  - `benchmark_intelligence/benchmark_summary_layer.py` (quoted:macro_benchmark_summary.txt)
- `macro_committee_summary.txt`
  - `strategic_intelligence/strategic_committee_engine.py` (quoted:macro_committee_summary.txt)
  - `benchmark_intelligence/macro_benchmark_engine.py` (quoted:macro_committee_summary.txt)
  - `macro_intelligence/macro_committee_engine.py` (quoted:macro_committee_summary.txt)
- `regional_benchmark_summary.txt`
  - `benchmark_intelligence/benchmark_summary_layer.py` (quoted:regional_benchmark_summary.txt)
  - `benchmark_intelligence/regional_benchmark_engine.py` (quoted:regional_benchmark_summary.txt)
- `sector_benchmark_summary.txt`
  - `benchmark_intelligence/benchmark_summary_layer.py` (quoted:sector_benchmark_summary.txt)
  - `benchmark_intelligence/sector_benchmark_engine.py` (quoted:sector_benchmark_summary.txt)
- `threshold_benchmark_summary.txt`
  - `benchmark_intelligence/benchmark_summary_layer.py` (quoted:threshold_benchmark_summary.txt)
  - `benchmark_intelligence/threshold_benchmark_engine.py` (quoted:threshold_benchmark_summary.txt)

### Root engine I/O (summaries/reports) (49)

- `backup_engine_report.txt`
  - `backup_engine.py` (quoted:backup_engine_report.txt)
- `candidate_recovery_summary.txt`
  - `candidate_recovery_engine.py` (quoted:candidate_recovery_summary.txt)
- `capital_flow_delta_summary.txt`
  - `strategic_intelligence/capital_flow_summary_layer.py` (quoted:capital_flow_delta_summary.txt)
  - `strategic_intelligence/capital_flow_delta.py` (quoted:capital_flow_delta_summary.txt)
- `capital_flow_momentum_summary.txt`
  - `strategic_intelligence/capital_flow_summary_layer.py` (quoted:capital_flow_momentum_summary.txt)
  - `strategic_intelligence/capital_flow_momentum.py` (quoted:capital_flow_momentum_summary.txt)
- `capital_flow_summary.txt`
  - `strategic_intelligence/capital_flow_summary_layer.py` (quoted:capital_flow_summary.txt)
- `cloud_backup_sync_report.txt`
  - `cloud_backup_sync.py` (quoted:cloud_backup_sync_report.txt)
- `confidence_adjustment_summary.txt`
  - `confidence_adjustment_engine.py` (quoted:confidence_adjustment_summary.txt)
  - `regime_forecast_layer.py` (quoted:confidence_adjustment_summary.txt)
- `economic_regime_summary.txt`
  - `macro_intelligence/macro_committee_engine.py` (quoted:economic_regime_summary.txt)
  - `macro_intelligence/economic_regime_engine.py` (quoted:economic_regime_summary.txt)
- `external_backup_sync_report.txt`
  - `external_backup_sync.py` (quoted:external_backup_sync_report.txt)
- `final_historical_intelligence_report.txt`
  - `final_historical_intelligence_report.py` (quoted:final_historical_intelligence_report.txt)
- `full_backup_runner_report.txt`
  - `full_backup_runner.py` (quoted:full_backup_runner_report.txt)
- `global_market_scanner_summary.txt`
  - `strategic_intelligence/strategic_intelligence_summary_layer.py` (quoted:global_market_scanner_summary.txt)
  - `strategic_intelligence/global_market_scanner.py` (quoted:global_market_scanner_summary.txt)
- `hard_risk_guardian_report.csv`
  - `hard_risk_guardian.py` (quoted:hard_risk_guardian_report.csv)
- `hard_risk_guardian_summary.txt`
  - `hard_risk_guardian.py` (quoted:hard_risk_guardian_summary.txt)
- `historical_committee_addon_summary.txt`
  - `confidence_adjustment_engine.py` (quoted:historical_committee_addon_summary.txt)
  - `historical_committee_addon.py` (quoted:historical_committee_addon_summary.txt)
  - `final_historical_intelligence_report.py` (quoted:historical_committee_addon_summary.txt)
- `historical_decision_alignment_summary.txt`
  - `historical_decision_alignment.py` (quoted:historical_decision_alignment_summary.txt)
  - `historical_committee_addon.py` (quoted:historical_decision_alignment_summary.txt)
  - `final_historical_intelligence_report.py` (quoted:historical_decision_alignment_summary.txt)
- `historical_intelligence_scores_summary.txt`
  - `final_historical_intelligence_report.py` (quoted:historical_intelligence_scores_summary.txt)
  - `historical_intelligence_scoring.py` (quoted:historical_intelligence_scores_summary.txt)
- `historical_outcome_summary.txt`
  - `historical_outcome_tracker.py` (quoted:historical_outcome_summary.txt)
- `inflation_intelligence_summary.txt`
  - `macro_intelligence/macro_committee_engine.py` (quoted:inflation_intelligence_summary.txt)
  - `macro_intelligence/inflation_intelligence_engine.py` (quoted:inflation_intelligence_summary.txt)
- `learning_engine_summary.txt`
  - `learning_engine.py` (quoted:learning_engine_summary.txt)
- `learning_feedback_summary.txt`
  - `learning_feedback_engine.py` (quoted:learning_feedback_summary.txt)
  - `confidence_adjustment_engine.py` (quoted:learning_feedback_summary.txt)
  - `regime_forecast_layer.py` (quoted:learning_feedback_summary.txt)
- `learning_insights_summary.txt`
  - `learning_insights.py` (quoted:learning_insights_summary.txt)
- `learning_recommendations_summary.txt`
  - `learning_recommendations.py` (quoted:learning_recommendations_summary.txt)
- `learning_scoreboard_summary.txt`
  - `learning_scoreboard.py` (quoted:learning_scoreboard_summary.txt)
- `morning_update_report.txt`
  - `morning_update.py` (quoted:morning_update_report.txt)
- `outcome_analytics_summary.txt`
  - `master_intelligence_score.py` (quoted:outcome_analytics_summary.txt)
  - `learning_health_engine.py` (quoted:outcome_analytics_summary.txt)
  - `outcome_analytics_engine.py` (quoted:outcome_analytics_summary.txt)
- `outcome_assignment_summary.txt`
  - `outcome_assignment_engine.py` (quoted:outcome_assignment_summary.txt)
- `post_sell_audit_report.csv`
  - `learning_engine.py` (quoted:post_sell_audit_report.csv)
  - `post_sell_audit.py` (quoted:post_sell_audit_report.csv)
- `post_sell_audit_summary.txt`
  - `post_sell_audit.py` (quoted:post_sell_audit_summary.txt)
- `rate_intelligence_summary.txt`
  - `macro_intelligence/macro_committee_engine.py` (quoted:rate_intelligence_summary.txt)
  - `macro_intelligence/rate_intelligence_engine.py` (quoted:rate_intelligence_summary.txt)
- `real_outcome_tracker_summary.txt`
  - `real_outcome_tracker.py` (quoted:real_outcome_tracker_summary.txt)
- `rebalance_edge_report.csv`
  - `learning_engine.py` (quoted:rebalance_edge_report.csv)
  - `rebalance_edge_engine.py` (quoted:rebalance_edge_report.csv)
- `rebalance_edge_summary.txt`
  - `rebalance_edge_engine.py` (quoted:rebalance_edge_summary.txt)
- `regime_intelligence_summary.txt`
  - `regime_forecast_layer.py` (quoted:regime_intelligence_summary.txt)
  - `regime_intelligence_engine.py` (quoted:regime_intelligence_summary.txt)
- `regional_strength_summary.txt`
  - `strategic_intelligence/strategic_intelligence_summary_layer.py` (quoted:regional_strength_summary.txt)
  - `strategic_intelligence/regional_strength_aggregator.py` (quoted:regional_strength_summary.txt)
- `score_threshold_audit_report.csv`
  - `learning_engine.py` (quoted:score_threshold_audit_report.csv)
  - `score_threshold_audit.py` (quoted:score_threshold_audit_report.csv)
- `score_threshold_audit_summary.txt`
  - `score_threshold_audit.py` (quoted:score_threshold_audit_summary.txt)
- `sector_flow_summary.txt`
  - `sector_intelligence/sector_flow_analyzer.py` (quoted:sector_flow_summary.txt)
  - `sector_intelligence/sector_rotation_summary_layer.py` (quoted:sector_flow_summary.txt)
- `sector_intelligence_summary.txt`
  - `sector_intelligence/sector_rotation_summary_layer.py` (quoted:sector_intelligence_summary.txt)
  - `strategic_intelligence/strategic_committee_engine.py` (quoted:sector_intelligence_summary.txt)
- `sector_momentum_summary.txt`
  - `sector_intelligence/sector_momentum_analyzer.py` (quoted:sector_momentum_summary.txt)
  - `sector_intelligence/sector_rotation_summary_layer.py` (quoted:sector_momentum_summary.txt)
- `sector_rotation_summary.txt`
  - `sector_intelligence/sector_rotation_scanner.py` (quoted:sector_rotation_summary.txt)
  - `sector_intelligence/sector_rotation_summary_layer.py` (quoted:sector_rotation_summary.txt)
- `signal_to_decision_summary.txt`
  - `signal_to_decision_engine.py` (quoted:signal_to_decision_summary.txt)
- `slot_pressure_summary.txt`
  - `slot_pressure_monitor.py` (quoted:slot_pressure_summary.txt)
- `strategic_allocation_summary.txt`
  - `strategic_intelligence/strategic_allocation_engine.py` (quoted:strategic_allocation_summary.txt)
  - `strategic_intelligence/strategic_intelligence_summary_layer.py` (quoted:strategic_allocation_summary.txt)
- `strategic_bias_summary.txt`
  - `strategic_intelligence/strategic_intelligence_summary_layer.py` (quoted:strategic_bias_summary.txt)
  - `strategic_intelligence/strategic_bias_engine.py` (quoted:strategic_bias_summary.txt)
- `strategic_intelligence_summary.txt`
  - `strategic_intelligence/strategic_committee_engine.py` (quoted:strategic_intelligence_summary.txt)
  - `strategic_intelligence/strategic_intelligence_summary_layer.py` (quoted:strategic_intelligence_summary.txt)
- `threshold_test_simulator_summary.txt`
  - `threshold_test_simulator.py` (quoted:threshold_test_simulator_summary.txt)
- `threshold_virtual_tracker_summary.txt`
  - `threshold_virtual_tracker.py` (quoted:threshold_virtual_tracker_summary.txt)
- `universe_from_candidates_summary.txt`
  - `universe_from_candidates.py` (quoted:universe_from_candidates_summary.txt)

### Other root .py references (4)

- `cloud_backup_sync.py`
  - `full_backup_runner.py` (quoted:cloud_backup_sync.py)
- `decision_registry_test.csv`
  - `outcome_evaluator_test.py` (quoted:decision_registry_test.csv)
- `external_backup_sync.py`
  - `full_backup_runner.py` (quoted:external_backup_sync.py)
- `v42_engine.py`
  - `autopilot.py` (import:v42_engine) — **only referenced by legacy `autopilot.py` (safe to move); treat as MOVE unless autopilot is reactivated**

### False positive (scanner artifact — keep as MOVE)

- `main.py` — matched `live_bot_v5_1.py` import of `research.multi_market_scanner.main` (function), not root `main.py`

---

## Files safe to move (49)

No references found from entry points, protected directories, or other project `.py`/`sh` files (excluding cleanup meta-artifacts).

### Portfolio / log before-snapshots (7)

- `bot_output_before_extra_cash_test.log`
- `portfolio_before_extra_cash_test.csv`
- `portfolio_before_v12_4_integrity_fix.csv`
- `portfolio_before_v36_6_integrity_cleanup.csv`
- `portfolio_before_v37_4_brkb_sell_correction.csv`
- `portfolio_before_v37_5_trailing_field_cleanup.csv`
- `portfolio_before_v38_1_buy_current_value_fix.csv`

### Crontab / shell before-snapshots (6)

- `committee_learning_engine_before_v9_6.py`
- `confidence_intelligence/weighted_committee_engine_before_v28_1.py`
- `crontab_backup_before_market_session_guard_20260624_094710.txt`
- `crontab_backup_before_runner_fix.txt`
- `market_open_runner_before_awake_guard_fix.sh`
- `market_open_runner_before_v37_7_fix.sh`

### Old logs (1)

- `bot_error_old.log`

### Version checkpoint status files (5)

- `V28_0_CHECKPOINT_STATUS.txt`
- `V29_0_STABLE_STATUS.txt`
- `V30_0_PROJECT_STATUS.txt`
- `V31_0_PROJECT_STATUS.txt`
- `V32_0_PROJECT_STATUS.txt`

### Legacy entrypoints / autopilots (7)

- `advanced_backtest.py`
- `autopilot.py`
- `backtest.py`
- `bot.py`
- `full_autopilot.py`
- `market_autopilot_final.py`
- `run_dashboard.py`

### Version audit / test scripts (17)

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

### Cleanup meta-artifacts (3)

- `project_cleanup_audit.py`
- `project_cleanup_audit_report.txt`
- `project_cleanup_delete_candidates_only.txt`

### Other (3)

- `Trading AI Dashboard.pdf`
- `outcome_evaluator_test.py`
- `watchlist_backup.txt` — only referenced by `auto_watchlist.py` (not in schedulers; safe unless cron uses it)

---

## Recommended manifest corrections

| Action | Count |
|--------|-------|
| Change `MOVE_TO_CLEANUP_ARCHIVE` → `KEEP` | 105 |
| False positive: retain as MOVE (`main.py`) | 1 |
| Retain `MOVE_TO_CLEANUP_ARCHIVE` | 49–50 |

After correction, **49–50 files** should remain quarantine candidates under `archive/cleanup_before_github/` (49 confirmed safe + optional `v42_engine.py` if legacy autopilot stays quarantined).

## Next step

Update `cleanup_before_github_manifest.csv` with corrected actions (not done in this pass). Then approve quarantine of the safe files only.