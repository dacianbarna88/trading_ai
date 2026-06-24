from pathlib import Path

FILES = [
    "capital_flow_delta_summary.txt",
    "capital_flow_momentum_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(Path(f).read_text())
    else:
        sections.append(f"MISSING: {f}")

summary = "\n\n".join([
    "===== V16.6.3 CAPITAL FLOW INTELLIGENCE SUMMARY =====",
    *sections,
    "FINAL CAPITAL FLOW VIEW:",
    "NO_CONFIRMED_ROTATION_YET",
    "",
    "Reason:",
    "Regional strength is stable and momentum history is still insufficient.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("capital_flow_summary.txt").write_text(summary)

print(summary)
