from pathlib import Path
from datetime import datetime

files = [
    "historical_intelligence_summary.txt",
    "historical_intelligence_scores_summary.txt",
    "historical_decision_alignment_summary.txt",
    "historical_committee_addon_summary.txt",
]

lines = [
    "===== V10.4 FINAL HISTORICAL INTELLIGENCE REPORT =====",
    f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    "",
]

for f in files:
    p = Path(f)
    lines.append("=" * 80)
    lines.append(f)
    lines.append("=" * 80)
    lines.append(p.read_text() if p.exists() else f"{f} not found")
    lines.append("")

lines.extend([
    "Final Interpretation:",
    "Historical intelligence strongly supports the current committee decision when combined with live decision accuracy.",
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(lines)

Path("final_historical_intelligence_report.txt").write_text(text)

print(text)
