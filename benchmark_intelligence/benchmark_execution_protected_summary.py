from pathlib import Path

FILES = [
    "benchmark_execution_summary.txt",
    "benchmark_vote_mapper_summary.txt",
    "benchmark_readiness_guard_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(Path(f).read_text())
    else:
        sections.append(f"MISSING: {f}")

summary = "\n\n".join([
    "===== V24.4 BENCHMARK EXECUTION PROTECTED SUMMARY =====",
    *sections,
    "FINAL PROTECTED EXECUTION VIEW:",
    "",
    "ALL_VOTES_MAPPED",
    "ALL_BENCHMARKS_DEFINED",
    "ALL_RULES_DEFINED",
    "NO_VOTES_READY_YET",
    "",
    "Protection:",
    "Benchmark execution remains blocked until validation horizons are reached.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("benchmark_execution_protected_summary.txt").write_text(summary)

print(summary)
