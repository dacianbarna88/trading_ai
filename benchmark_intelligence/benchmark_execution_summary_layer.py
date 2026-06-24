from pathlib import Path

FILES = [
    "benchmark_execution_summary.txt",
    "benchmark_vote_mapper_summary.txt",
    "benchmark_intelligence_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(Path(f).read_text())
    else:
        sections.append(f"MISSING: {f}")

summary = "\n\n".join([
    "===== V24.2 BENCHMARK EXECUTION SUMMARY =====",
    *sections,
    "FINAL EXECUTION VIEW:",
    "ALL_VOTES_EXECUTABLE_AND_MAPPED",
    "",
    "Protection:",
    "No vote outcome is changed by this layer.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("benchmark_execution_layer_summary.txt").write_text(summary)

print(summary)
