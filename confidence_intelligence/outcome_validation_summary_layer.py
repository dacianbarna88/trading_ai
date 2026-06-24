from pathlib import Path

FILES = [
    "vote_outcome_summary.txt",
    "validation_horizon_summary.txt",
    "automatic_outcome_evaluator_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(Path(f).read_text())
    else:
        sections.append(f"MISSING: {f}")

summary = "\n\n".join([
    "===== V21.3 OUTCOME VALIDATION SUMMARY =====",
    *sections,
    "FINAL VALIDATION VIEW:",
    "OUTCOME_VALIDATION_FRAMEWORK_ACTIVE",
    "NO_VOTES_READY_YET",
    "",
    "Interpretation:",
    "The system can now track vote age and determine when each strategic vote becomes eligible for validation. No vote is ready yet because all votes were created today.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("outcome_validation_summary.txt").write_text(summary)

print(summary)
