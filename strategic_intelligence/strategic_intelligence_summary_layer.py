from pathlib import Path

FILES = [
    "global_market_scanner_summary.txt",
    "regional_strength_summary.txt",
    "strategic_bias_summary.txt",
    "strategic_allocation_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(Path(f).read_text())
    else:
        sections.append(f"MISSING: {f}")

summary = "\n\n".join([
    "===== V16.5 STRATEGIC INTELLIGENCE SUMMARY LAYER =====",
    *sections,
    "FINAL STRATEGIC VIEW:",
    "OVERWEIGHT_US",
    "NEUTRAL_EUROPE",
    "UNDERWEIGHT_UK",
    "UNDERWEIGHT_ASIA",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("strategic_intelligence_summary.txt").write_text(summary)

print(summary)
