from pathlib import Path

FILES = [
    "sector_rotation_summary.txt",
    "sector_flow_summary.txt",
    "sector_momentum_summary.txt",
]

sections = []

for f in FILES:
    if Path(f).exists():
        sections.append(Path(f).read_text())
    else:
        sections.append(f"MISSING: {f}")

summary = "\n\n".join([
    "===== V17.4 SECTOR ROTATION INTELLIGENCE =====",
    *sections,
    "FINAL SECTOR VIEW:",
    "OVERWEIGHT_TECHNOLOGY",
    "WATCH_INDUSTRIALS",
    "WATCH_MATERIALS",
    "UNDERWEIGHT_COMMUNICATIONS",
    "",
    "Reason:",
    "Technology is the dominant sector leader. Industrials and Materials are second-wave strength candidates. Sector flow and momentum require more history.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

Path("sector_intelligence_summary.txt").write_text(summary)

print(summary)
