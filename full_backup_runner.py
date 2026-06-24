from pathlib import Path
from datetime import datetime
import subprocess

TASKS = [
    "backup_engine.py",
    "cloud_backup_sync.py",
    "external_backup_sync.py",
]

OUTPUT = "full_backup_runner_report.txt"

report = []

report.append("===== V32.8 FULL BACKUP RUNNER =====")
report.append("")
report.append(f"Timestamp: {datetime.now()}")
report.append("")

success = 0

for task in TASKS:

    report.append(f"Running: {task}")

    if not Path(task).exists():
        report.append("STATUS: MISSING")
        report.append("")
        continue

    result = subprocess.run(
        ["python3", task],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        report.append("STATUS: OK")
        success += 1
    else:
        report.append("STATUS: ERROR")
        report.append(result.stderr)

    report.append("")

report.append(f"Successful Backup Tasks: {success}/{len(TASKS)}")
report.append("")
report.append("Backup Targets:")
report.append("- Local backups/")
report.append("- iCloud Drive / TradingAI_Backups")
report.append("- PortableSSD / TradingAI_Backups")
report.append("")
report.append("Mode:")
report.append("BACKUP_ONLY")
report.append("NO_TRADING_CHANGE")
report.append("NO_BROKER")

text = "\n".join(report)

Path(OUTPUT).write_text(text)

print(text)
