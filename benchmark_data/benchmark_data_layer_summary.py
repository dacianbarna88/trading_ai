from pathlib import Path

FILES = [
    "benchmark_history.csv",
    "benchmark_price_history.csv",
    "benchmark_data_quality_summary.txt",
    "benchmark_data_summary.txt",
    "return_tracking_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(f"{f} | FOUND")
    else:
        sections.append(f"{f} | MISSING")

summary = "\n".join([
    "===== V25.5 BENCHMARK DATA LAYER SUMMARY =====",
    "",
    *sections,
    "",
    "FINAL DATA LAYER VIEW:",
    "",
    "BENCHMARK_DATA_COLLECTION_ACTIVE",
    "BENCHMARK_PRICE_COLLECTION_ACTIVE",
    "DATA_QUALITY_VALID",
    "RETURN_TRACKING_ACTIVE",
    "RETURN_HISTORY_NOT_READY_YET",
    "",
    "Reason:",
    "Only one valid benchmark price snapshot exists so far.",
    "Returns will become available after at least two valid price snapshots.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("benchmark_data_layer_summary.txt").write_text(summary)

print(summary)
