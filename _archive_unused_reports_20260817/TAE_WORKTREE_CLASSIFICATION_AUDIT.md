# TAE Worktree Classification Audit

**Mode:** READ-ONLY · NO CLEAN · NO COMMIT
**Generated:** 2026-07-24T10:34:10.715154+03:00

## Totals

| Metric | Count |
| --- | ---: |
| Modified | 77 |
| Untracked | 39 |
| Reviewed | 116 |
| AUDIT_EVIDENCE | 36 |
| CANONICAL_DOCUMENTATION | 6 |
| GENERATED_REPORT | 61 |
| GENERATED_RUNTIME_ARTIFACT | 13 |

## Independent check vs Quick Health

Quick Health claimed `operationally_relevant=0`, `generated_artifacts=116`.

- **No dirty `.py` / `.sh` / `.plist` / config** found.
- **No live BUY-path inputs** among dirty files.
- **Canonical documentation exceptions** exist (QH still buckets them as generated for BUY-gate — acceptable for trading readiness, incomplete for commit hygiene).
- **Learning/attribution JSON/CSV** are regenerable experiment artifacts but **continuity-sensitive**; do not auto-delete.
- **`tae_*.md` with `.py` twins** are generated reports (`OUTPUT_MD`), not source duplicates.

### Misclassified notes (hygiene, not BUY)
- TAE_E3_FORWARD_PAPER_SPEC.md: QH=generated (OK for BUY-gate) but audit=CANONICAL_DOCUMENTATION (commit hygiene)
- TAE_FORWARD_LEARNING_EVIDENCE_MONITOR.md: QH=generated (OK for BUY-gate) but audit=CANONICAL_DOCUMENTATION (commit hygiene)
- TAE_LEARNING_ECONOMIC_ATTRIBUTION.md: QH=generated (OK for BUY-gate) but audit=CANONICAL_DOCUMENTATION (commit hygiene)
- TAE_LEARNING_ECONOMIC_ROBUSTNESS.md: QH=generated (OK for BUY-gate) but audit=CANONICAL_DOCUMENTATION (commit hygiene)
- TAE_OPENING_NOISE_CANONICAL_IMPLEMENTATION.md: QH=generated (OK for BUY-gate) but audit=CANONICAL_DOCUMENTATION (commit hygiene)
- TAE_OPENING_NOISE_CANONICAL_VALIDATION.md: QH=generated (OK for BUY-gate) but audit=CANONICAL_DOCUMENTATION (commit hygiene)

## Strategic document recommendations

| Path | Recommendation |
| --- | --- |
| `TAE_MASTER_STRATEGIC_REVIEW.md` | KEEP_AND_COMMIT |
| `TAE_MASTER_STRATEGIC_EVIDENCE.md` | KEEP_AND_COMMIT |
| `TAE_EXECUTIVE_VERDICT.md` | KEEP_AND_COMMIT |
| `TAE_EXECUTIVE_VERDICT_COMPLIANCE.md` | KEEP_AND_COMMIT |
| `TAE_CHAPTER_RECONCILIATION.md` | KEEP_BUT_ARCHIVE |
| `TAE_SELF_LEARNING_EVIDENCE.md` | KEEP_AND_COMMIT |
| `TAE_SPRINT1_IMPLEMENTATION_DESIGN.md` | KEEP_AND_COMMIT |
| `TAE_INTEGRATION_MATRIX.md` | KEEP_AND_COMMIT |
| `TAE_DPE3_REUSE_MATRIX.md` | KEEP_AND_COMMIT |

## Learning/attribution state protected

- `tae_30_day_paper_profit_validation.json`
- `tae_forward_learning_evidence_status.json`
- `tae_learning_ablation_runs.json`
- `tae_learning_ablation_summary.json`
- `tae_learning_decision_deltas.csv`
- `tae_learning_economic_attribution.csv`
- `tae_learning_economic_attribution.json`
- `tae_learning_trade_deltas.csv`
- `tae_roi_queue.json`

## Full file classification

| path | git | category | gen | runtime_in | runtime_out | can_src | can_doc | regen | action | evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `TAE_ADAPTIVE_WEIGHTS_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_BASELINE_VS_CHALLENGERS_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_CAPITAL_BASE_INTEGRITY_AUDIT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_CONFLICT_RESOLUTION_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_DECISION_DISCIPLINE_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_DECISION_STATE_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_E3_FORWARD_PAPER_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_E3_FORWARD_PAPER_SPEC.md` | modified | CANONICAL_DOCUMENTATION | no | no | no | no | yes | no | KEEP_AND_COMMIT | force-tracked canonical implementation/spec; not BUY-path input |
| `TAE_ECONOMIC_DATA_INTEGRITY_AUDIT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_FORWARD_LEARNING_EVIDENCE_MONITOR.md` | modified | CANONICAL_DOCUMENTATION | yes | no | no | no | yes | unknown | KEEP_AND_COMMIT_IF_INTENTIONALLY_TRACKED | force-tracked learning economic documentation family |
| `TAE_FULL_PAPER_CYCLE_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_HISTORICAL_RUNTIME_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_INVESTMENT_COUNCIL_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_LEARNING_ECONOMIC_ABLATION_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_LEARNING_ECONOMIC_ATTRIBUTION.md` | modified | CANONICAL_DOCUMENTATION | yes | no | no | no | yes | unknown | KEEP_AND_COMMIT_IF_INTENTIONALLY_TRACKED | force-tracked learning economic documentation family |
| `TAE_LEARNING_ECONOMIC_ROBUSTNESS.md` | modified | CANONICAL_DOCUMENTATION | yes | no | no | no | yes | unknown | KEEP_AND_COMMIT_IF_INTENTIONALLY_TRACKED | force-tracked learning economic documentation family |
| `TAE_LEARNING_TO_PROFIT_BRIDGE_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_LIVE_PROMOTION_LOCK_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_OPENING_NOISE_CANONICAL_IMPLEMENTATION.md` | modified | CANONICAL_DOCUMENTATION | no | no | no | no | yes | no | KEEP_AND_COMMIT | force-tracked canonical implementation/spec; not BUY-path input |
| `TAE_OPENING_NOISE_CANONICAL_VALIDATION.md` | modified | CANONICAL_DOCUMENTATION | no | no | no | no | yes | no | KEEP_AND_COMMIT | force-tracked canonical implementation/spec; not BUY-path input |
| `TAE_PAPER_DECISION_ENGINE_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_PAPER_DECISION_VALIDATION_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_PAPER_EXPERIMENT_RUNNER_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_PAPER_PROFIT_INTEGRITY_GUARD_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_PROFIT_OPTIMIZATION_AUDIT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_PROFIT_PIPELINE_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_ROI001_CHALLENGER_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_STRUCTURAL_CONSOLIDATION_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `TAE_STRUCTURAL_GOVERNANCE_REPORT.md` | modified | GENERATED_REPORT | yes | no | no | no | no | yes | REGENERATE_OR_DISCARD_LOCAL | tracked TAE report/audit markdown (often under TAE_*_REPORT ignore with exceptio |
| `tae_30_day_paper_profit_validation.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | yes | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_accounting_snapshot.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_accounting_snapshot.py (OUTPUT_MD); not imported a |
| `tae_adaptive_profit_policy_engine.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_adaptive_profit_policy_engine.py (OUTPUT_MD); not  |
| `tae_baseline_vs_challengers.json` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | generated json/csv report artifact |
| `tae_confidence_evolution.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_confidence_evolution.py (OUTPUT_MD); not imported  |
| `tae_decision_event_bus.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_decision_event_bus.py (OUTPUT_MD); not imported as |
| `tae_decision_governor.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_decision_governor.py (OUTPUT_MD); not imported as  |
| `tae_decision_replay.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | yes | yes | no | no | yes | PERSIST_OR_IGNORE_REGENERABLE | generated JSON runtime/report artifact; force-tracked or regenerated |
| `tae_decision_replay.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | tae_*.md derived report/summary |
| `tae_e3_forward_paper.json` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | generated json/csv report artifact |
| `tae_economic_orchestration_closure_audit.json` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | generated json/csv report artifact |
| `tae_execution_splitter.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_execution_splitter.py (OUTPUT_MD); not imported as |
| `tae_executive_review_ssot_audit.json` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | generated json/csv report artifact |
| `tae_forward_learning_evidence_status.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | yes | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_growth_intelligence.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_growth_intelligence.py (OUTPUT_MD); not imported a |
| `tae_infrastructure_health.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_infrastructure_health.py (OUTPUT_MD); not imported |
| `tae_intraday_discovery_engine.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_intraday_discovery_engine.py (OUTPUT_MD); not impo |
| `tae_intraday_fade_history_summary.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | tae_*.md derived report/summary |
| `tae_intraday_fade_intelligence.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_intraday_fade_intelligence.py (OUTPUT_MD); not imp |
| `tae_knowledge_base.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_knowledge_base.py (OUTPUT_MD); not imported as sou |
| `tae_knowledge_summary.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | tae_*.md derived report/summary |
| `tae_learning_ablation_runs.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | no | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_learning_ablation_summary.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | no | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_learning_decision_deltas.csv` | modified | GENERATED_RUNTIME_ARTIFACT | yes | no | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_learning_economic_attribution.csv` | modified | GENERATED_RUNTIME_ARTIFACT | yes | no | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_learning_economic_attribution.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | no | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_learning_trade_deltas.csv` | modified | GENERATED_RUNTIME_ARTIFACT | yes | no | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_market_open_intelligence_runner.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_market_open_intelligence_runner.py (OUTPUT_MD); no |
| `tae_next_dollar.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | yes | yes | no | no | yes | PERSIST_OR_IGNORE_REGENERABLE | generated JSON runtime/report artifact; force-tracked or regenerated |
| `tae_opportunity_cost_ledger.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_opportunity_cost_ledger.py (OUTPUT_MD); not import |
| `tae_paper_profit_integrity_guard_report.json` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | generated json/csv report artifact |
| `tae_phase_x_master_economic_validation.json` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | generated json/csv report artifact |
| `tae_portfolio_profit_governor.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_portfolio_profit_governor.py (OUTPUT_MD); not impo |
| `tae_profit_committee_learning.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_profit_committee_learning.py (OUTPUT_MD); not impo |
| `tae_profit_context_engine.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_profit_context_engine.py (OUTPUT_MD); not imported |
| `tae_profit_context_learning.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | tae_*.md derived report/summary |
| `tae_profit_decision_committee.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_profit_decision_committee.py (OUTPUT_MD); not impo |
| `tae_profit_decision_governor.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_profit_decision_governor.py (OUTPUT_MD); not impor |
| `tae_profit_intelligence_brain.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_profit_intelligence_brain.py (OUTPUT_MD); not impo |
| `tae_profit_memory_engine.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_profit_memory_engine.py (OUTPUT_MD); not imported  |
| `tae_profit_optimization_audit.json` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | generated json/csv report artifact |
| `tae_profit_pipeline.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | yes | yes | no | no | yes | PERSIST_OR_IGNORE_REGENERABLE | generated JSON runtime/report artifact; force-tracked or regenerated |
| `tae_profit_protection_shadow.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_profit_protection_shadow.py (OUTPUT_MD); not impor |
| `tae_profit_protection_validation.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_profit_protection_validation.py (OUTPUT_MD); not i |
| `tae_roi001_challenger_report.json` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | generated json/csv report artifact |
| `tae_roi_queue.json` | modified | GENERATED_RUNTIME_ARTIFACT | yes | yes | yes | no | no | no | PERSIST_IGNORE_OR_ARCHIVE_DO_NOT_DELETE | learning/attribution/ROI experiment artifact; .gitignore force-tracked; not live |
| `tae_stop_reentry_cooldown_audit.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_stop_reentry_cooldown_audit.py (OUTPUT_MD); not im |
| `tae_winner_lifecycle_profiler.md` | modified | GENERATED_REPORT | yes | no | yes | no | no | yes | DO_NOT_COMMIT_REGENERATE | auto-written companion of tae_winner_lifecycle_profiler.py (OUTPUT_MD); not impo |
| `TAE_CHAPTER_1_DEFENSE.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_1_INVESTMENT_THESIS.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_2_DEFENSE.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_2_ECONOMIC_ARCHITECTURE.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_2_PASSIVE_COMPLEXITY_PROOF.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_3_DECISION_ARCHITECTURE.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_3_DECISION_OWNERSHIP_PROOF.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_4_DECISION_TO_FILL_STALENESS_PROOF.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_4_EXECUTION_PROOF.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_5_ECONOMIC_ATTRIBUTION_PROOF.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_5_LEARNING_PROOF.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_5_LEARNING_SYSTEM.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_6_COMPLEXITY_PROOF.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_7_INSTITUTIONAL_PROOF.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_7_INSTITUTIONAL_READINESS.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_CHAPTER_RECONCILIATION.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_DPE3_REUSE_MATRIX.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_AND_COMMIT | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_DPE_FOUNDATION_SCORECARD.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_DPE_VALIDATION_START_GATE.md` | untracked | GENERATED_REPORT | yes | no | no | no | no | yes | GENERATE_ON_DEMAND | generated by TAE_DPE_VALIDATION_START_GATE.py / gate module |
| `TAE_EXECUTION_ELIGIBILITY_FORENSIC.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_EXECUTIVE_REVIEW.md` | untracked | GENERATED_REPORT | yes | no | no | no | no | yes | GENERATE_ON_DEMAND | generated by tae_executive_review.py |
| `TAE_EXECUTIVE_VERDICT.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_AND_COMMIT | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_EXECUTIVE_VERDICT_COMPLIANCE.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_AND_COMMIT | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_FORENSIC_LOSS_AUTOPSY.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_INTEGRATION_MATRIX.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_AND_COMMIT | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_MASTER_CONTEXT.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_MASTER_STRATEGIC_EVIDENCE.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_AND_COMMIT | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_MASTER_STRATEGIC_REVIEW.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_AND_COMMIT | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_OPPORTUNITY_DEATH_MAP.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_PROFIT_EDGE_DISCOVERY.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_PROFIT_PIPELINE_SEMANTICS_FIX.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_PROMISING_TO_PROFIT_VERIFICATION.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_RETROSPECTIVE_LEARNING_CAUSAL_AUDIT.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_SAME_ACTION_FORENSIC.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_SELF_LEARNING_EVIDENCE.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_AND_COMMIT | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_SPRINT1_IMPLEMENTATION_DESIGN.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_AND_COMMIT | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_TOP10_PROFIT_OPPORTUNITIES.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | untracked strategic/forensic/chapter narrative — not runtime input |
| `TAE_UNTRACKED_DOCUMENT_CLASSIFICATION.md` | untracked | AUDIT_EVIDENCE | no | no | no | no | no | no | KEEP_BUT_ARCHIVE | prior document classification audit |
| `tae_growth_intelligence.json` | untracked | GENERATED_RUNTIME_ARTIFACT | yes | yes | yes | no | no | yes | PERSIST_OR_IGNORE_REGENERABLE | growth intelligence SSOT JSON; force-tracked exception; not live_bot BUY literal |

## Git verdict

`WORKTREE_MOSTLY_GENERATED_WITH_CANONICAL_EXCEPTIONS`

- SAFE TO CLEAN AUTOMATICALLY: NO
- SAFE TO COMMIT AUTOMATICALLY: NO
- MANUAL REVIEW REQUIRED: YES

## Proposed Git policy

1. Track canonical source (.py/.sh/.plist) and intentional SSOT docs (E3 SPEC, opening-noise canonical, learning design docs).
2. Ignore regenerable TAE_*_REPORT.md and tae_* module companion .md reports by default.
3. Persist but ignore (or archive) high-churn runtime JSON under runtime_outputs/; keep explicit !exceptions only for experiment continuity ledgers.
4. Archive historical strategic chapter/forensic markdown under docs/archive/ after review — do not delete experiment evidence casually.
5. Operator-facing canonical reports that must stay reviewed should be force-tracked exceptions with owners, not blanket generated noise.

