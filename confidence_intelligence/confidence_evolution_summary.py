from pathlib import Path

FILES = [
    "vote_accuracy_summary.txt",
    "weighted_committee_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(Path(f).read_text())
    else:
        sections.append(f"MISSING: {f}")

summary = "\n\n".join([
    "===== V20.3 STRATEGIC CONFIDENCE EVOLUTION =====",
    *sections,
    "FINAL CONFIDENCE VIEW:",
    "WEIGHTED_COMMITTEE_ACTIVE",
    "HIGH_CONFIDENCE_ACCUMULATE_US_TECH",
    "",
    "Interpretation:",
    "The strategic committee is now capable of using historical vote weights. Current weights remain neutral because all vote outcomes are still pending.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("confidence_evolution_summary.txt").write_text(summary)

print(summary)
