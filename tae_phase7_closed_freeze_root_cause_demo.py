from research_core.legacy_freeze.closed_freeze_report import (
    build_closed_freeze_report,
    save_report,
)

print("===== TAE PHASE VII A5 — LEGACY CLOSED_FREEZE ROOT CAUSE =====")
print("ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION")

report = build_closed_freeze_report()
save_report(report)

print("Verdict:", report.verdict)
print("Current Score 100+ PnL:", report.score100_current_pnl)
print("Legacy CLOSED_FREEZE Score 100+ PnL:", report.score100_legacy_pnl)
print("Delta:", report.anomaly_delta)
print("JSON saved: tae_closed_freeze_root_cause.json")
print("TXT saved: tae_closed_freeze_root_cause.txt")
