from pathlib import Path
from datetime import datetime
import subprocess

TASKS = [
    "daily_intelligence_runner.py",
    "market_open_readiness.py",
    "market_readiness_score.py",
    "master_intelligence_score.py",
    "project_map_generator.py",
]

OUTPUT = "morning_update_report.txt"

report = []

report.append(
    "===== V32.4 MORNING UPDATE ====="
)
report.append("")
report.append(
    f"Timestamp: {datetime.now()}"
)
report.append("")

success = 0

for task in TASKS:

    report.append(
        f"Running: {task}"
    )

    if not Path(task).exists():

        report.append(
            "STATUS: MISSING"
        )
        report.append("")
        continue

    try:

        result = subprocess.run(
            ["python3", task],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:

            report.append(
                "STATUS: OK"
            )

            success += 1

        else:

            report.append(
                "STATUS: ERROR"
            )

        report.append("")

    except Exception as e:

        report.append(
            f"STATUS: EXCEPTION {e}"
        )

        report.append("")

report.append(
    f"Successful Tasks: {success}/{len(TASKS)}"
)

report.append("")
report.append("Mode:")
report.append("ANALYSIS_ONLY")
report.append("PAPER_ONLY")
report.append("NO_BROKER")
report.append("NO_AUTO_EXECUTION")

text = "\n".join(report)

Path(OUTPUT).write_text(text)

print(text)
