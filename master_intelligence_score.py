from pathlib import Path
import re

OUTPUT = "master_intelligence_score_summary.txt"


def extract_score(path, label):
    if not Path(path).exists():
        return 0

    text = Path(path).read_text()

    for line in text.splitlines():
        if label in line:
            match = re.search(r"(\d+\.?\d*)", line)
            if match:
                return float(match.group(1))

    return 0


market_readiness = extract_score(
    "market_readiness_score_summary.txt",
    "Final Readiness Score"
)

learning_health = extract_score(
    "learning_health_summary.txt",
    "Learning Health Score"
)

decision_quality = 0
if Path("decision_quality_summary.txt").exists():
    text = Path("decision_quality_summary.txt").read_text()

    if "Decision Quality: EXCELLENT" in text:
        decision_quality = 90
    elif "Decision Quality: GOOD" in text:
        decision_quality = 75
    elif "Decision Quality: NEUTRAL" in text:
        decision_quality = 55
    elif "Decision Quality: INSUFFICIENT_DATA" in text:
        decision_quality = 30

calibration_score = 0
if Path("confidence_calibration_summary.txt").exists():
    text = Path("confidence_calibration_summary.txt").read_text()

    if "Completed Decisions: 0" in text:
        calibration_score = 25
    else:
        calibration_score = 60

outcome_score = 0
if Path("outcome_analytics_summary.txt").exists():
    text = Path("outcome_analytics_summary.txt").read_text()

    if "No completed outcomes available" in text:
        outcome_score = 25
    else:
        outcome_score = 60

master_score = round(
    (
        market_readiness * 0.30
        + learning_health * 0.30
        + decision_quality * 0.15
        + calibration_score * 0.15
        + outcome_score * 0.10
    ),
    2
)

if master_score >= 80:
    status = "STRONG_OPERATIONAL"
elif master_score >= 65:
    status = "OPERATIONAL"
elif master_score >= 50:
    status = "DEVELOPING"
else:
    status = "LIMITED"

summary = f"""
===== V30.8 MASTER INTELLIGENCE SCORE =====

Market Readiness: {market_readiness}
Learning Health: {learning_health}
Decision Quality Score: {decision_quality}
Confidence Calibration Score: {calibration_score}
Outcome Analytics Score: {outcome_score}

Master Intelligence Score: {master_score}/100

Status: {status}

Interpretation:
The platform infrastructure is active.
The main limitation remains lack of completed WIN/LOSS outcomes.

Mode:
ANALYSIS_ONLY
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path(OUTPUT).write_text(summary)

print(summary)
