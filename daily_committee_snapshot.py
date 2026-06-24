from pathlib import Path
from datetime import datetime

files = [
    "strategic_committee_summary.txt",
    "portfolio_action_summary.txt",
    "decision_accuracy_report.txt",
    "committee_learning_summary.txt",
    "committee_learning_analytics.txt",
]

snapshot_dir = Path("daily_committee_snapshots")
snapshot_dir.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
snapshot_file = snapshot_dir / f"committee_snapshot_{timestamp}.txt"

lines = [
    "===== DAILY COMMITTEE SNAPSHOT =====",
    f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    "",
]

for file in files:
    path = Path(file)
    lines.append("=" * 80)
    lines.append(file)
    lines.append("=" * 80)
    lines.append(path.read_text() if path.exists() else f"{file} not found")
    lines.append("")

lines.extend([
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(lines)
snapshot_file.write_text(text)
Path("latest_committee_snapshot.txt").write_text(text)

print(text)
print()
print(f"Snapshot saved: {snapshot_file}")
