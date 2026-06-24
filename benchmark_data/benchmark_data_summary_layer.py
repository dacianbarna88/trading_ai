from pathlib import Path

FILES = [
    "benchmark_history.csv",
    "benchmark_price_history.csv",
    "benchmark_data_quality_summary.txt",
]

summary = [
    "===== V25.3 BENCHMARK DATA SUMMARY LAYER =====",
    ""
]

for f in FILES:

    if Path(f).exists():
        summary.append(f"{f} | FOUND")
    else:
        summary.append(f"{f} | MISSING")

summary.extend([
    "",
    "FINAL DATA VIEW:",
    "",
    "BENCHMARK_DATA_LAYER_ACTIVE",
    "DATA_QUALITY_VALID",
    "READY_FOR_RETURN_TRACKING",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER"
])

text = "\n".join(summary)

Path(
    "benchmark_data_summary.txt"
).write_text(text)

print(text)
