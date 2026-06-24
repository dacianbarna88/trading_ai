from pathlib import Path
import pandas as pd

score = 0
max_score = 100

# Infrastructure (40p)
required_files = [
    "decision_registry.csv",
    "adaptive_weights.csv",
    "learning_weight_history.csv",
    "market_session_snapshots.csv",
    "session_intelligence_summary.txt",
]

infra_score = 0

for f in required_files:
    if Path(f).exists():
        infra_score += 8

score += infra_score

# Decision Confidence (20p)
confidence_score = 0

if Path("weighted_committee_summary.txt").exists():

    text = Path(
        "weighted_committee_summary.txt"
    ).read_text()

    for line in text.splitlines():

        if "Weighted Confidence:" in line:

            try:
                value = float(
                    line.split(":")[1]
                    .replace("%", "")
                    .strip()
                )

                confidence_score = min(
                    20,
                    round(value / 5)
                )

            except:
                pass

score += confidence_score

# Decision History (20p)

history_score = 0

if Path("decision_registry.csv").exists():

    df = pd.read_csv(
        "decision_registry.csv"
    )

    history_score = min(
        20,
        len(df) * 2
    )

score += history_score

# Session Intelligence (20p)

session_score = 0

if Path(
    "market_session_snapshots.csv"
).exists():

    snapshots = pd.read_csv(
        "market_session_snapshots.csv"
    )

    session_score = min(
        20,
        len(snapshots) * 2
    )

score += session_score

readiness = round(score, 1)

if readiness >= 80:
    status = "READY"

elif readiness >= 60:
    status = "CAUTION"

else:
    status = "NOT_READY"

summary = f"""
===== V29.8 MARKET READINESS SCORE =====

Infrastructure Score: {infra_score}/40
Confidence Score: {confidence_score}/20
History Score: {history_score}/20
Session Score: {session_score}/20

Final Readiness Score: {readiness}/100

Status: {status}

Mode:
ANALYSIS_ONLY
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path(
    "market_readiness_score_summary.txt"
).write_text(summary)

print(summary)
