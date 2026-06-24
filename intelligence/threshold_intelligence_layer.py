from pathlib import Path

FILES = {
    "outcome": "threshold_outcome_summary.txt",
    "decision": "threshold_decision_summary.txt",
    "confidence": "threshold_confidence_summary.txt",
    "history": "threshold_history_summary.txt",
}

sections = []

for name, path in FILES.items():
    if Path(path).exists():
        sections.append(Path(path).read_text())
    else:
        sections.append(f"{name.upper()}: MISSING")

summary = "\n\n".join([
    "===== V15.0 THRESHOLD INTELLIGENCE LAYER =====",
    *sections,
    "FINAL STRATEGIC POSITION:",
    "KEEP_THRESHOLD_90_UNTIL_MORE_DATA",
    "",
    "Mode:",
    "AUDIT_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("threshold_intelligence_summary.txt").write_text(summary)

print(summary)
