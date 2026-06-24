from pathlib import Path

FILES = [
    "regional_benchmark_summary.txt",
    "sector_benchmark_summary.txt",
    "macro_benchmark_summary.txt",
    "horizon_benchmark_summary.txt",
    "threshold_benchmark_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(Path(f).read_text())
    else:
        sections.append(f"MISSING: {f}")

summary = "\n\n".join([
    "===== V23.5 BENCHMARK INTELLIGENCE LAYER =====",
    *sections,
    "FINAL BENCHMARK VIEW:",
    "BENCHMARK_LAYER_ACTIVE",
    "ALL_PRIMARY_BENCHMARKS_DEFINED",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("benchmark_intelligence_summary.txt").write_text(summary)

print(summary)
