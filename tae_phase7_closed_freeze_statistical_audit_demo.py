from research_core.statistical_validation.closed_freeze_statistical_audit import (
    build_report,
    save_report,
)

print("===== TAE PHASE VII A6 — CLOSED_FREEZE STATISTICAL VALIDATION AUDIT =====")
print("ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION")

report = build_report()
save_report(report)

print("Verdict:", report.verdict)
print("All Score 100+ total PnL:", report.all_score100.total_pnl)
print("Current Score 100+ total PnL:", report.current_score100.total_pnl)
print("Legacy CLOSED_FREEZE Score 100+ total PnL:", report.legacy_closed_freeze_score100.total_pnl)
print("Delta total:", report.delta_current_vs_legacy_total_pnl)
print("Delta expectancy:", report.delta_current_vs_legacy_expectancy)
print("JSON saved: tae_closed_freeze_statistical_audit.json")
print("TXT saved: tae_closed_freeze_statistical_audit.txt")
