from pathlib import Path
import subprocess

ENGINES = [
    "outcome_evaluator.py",
    "feedback_update_engine.py",
    "decision_quality_engine.py",
    "confidence_calibration_engine.py",
    "decision_replay_engine.py",
    "pattern_discovery_engine.py",
    "learning_recommendations_engine.py",
    "confidence_optimizer_engine.py",
    "master_intelligence_score.py",
]

OUTPUT = "daily_intelligence_report.txt"

report = []

report.append(
    "===== V32.1 DAILY INTELLIGENCE RUNNER ====="
)
report.append("")

for engine in ENGINES:

    report.append(
        f"Running: {engine}"
    )

    if not Path(engine).exists():

        report.append(
            "STATUS: MISSING"
        )

        report.append("")
        continue

    try:

        result = subprocess.run(
            ["python3", engine],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            report.append(
                "STATUS: OK"
            )
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

report.extend([
    "Summary:",
    f"Engines Checked: {len(ENGINES)}",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(report)

Path(OUTPUT).write_text(text)

print(text)
