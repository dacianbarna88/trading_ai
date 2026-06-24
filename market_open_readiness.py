from pathlib import Path
from datetime import datetime
import pandas as pd

FILES = [
    "decision_registry.csv",
    "adaptive_weights.csv",
    "learning_weight_history.csv",
    "strategic_committee_summary.txt",
    "weighted_committee_summary.txt",
    "adaptive_decision_guard_summary.txt",
    "outcome_evaluator_summary.txt",
    "feedback_update_summary.txt",
]

summary = []
score = 0
max_score = len(FILES)

summary.append("===== V29.3 MARKET OPEN READINESS PACK =====")
summary.append("")
summary.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
summary.append("")

summary.append("Required Files:")

for f in FILES:
    if Path(f).exists():
        summary.append(f"{f} | OK")
        score += 1
    else:
        summary.append(f"{f} | MISSING")

readiness = round(score / max_score * 100, 2)

summary.append("")
summary.append(f"Readiness Score: {readiness}%")
summary.append("")

if readiness >= 90:
    status = "READY_FOR_MARKET_MONITORING"
elif readiness >= 70:
    status = "PARTIALLY_READY"
else:
    status = "NOT_READY"

summary.append(f"Status: {status}")
summary.append("")

if Path("decision_registry.csv").exists():
    df = pd.read_csv("decision_registry.csv")
    pending = df[df["Outcome"] == "PENDING"]

    summary.append(f"Decision Records: {len(df)}")
    summary.append(f"Pending Outcomes: {len(pending)}")

    if len(pending) > 0:
        summary.append("")
        summary.append("Pending Decisions:")
        for _, row in pending.iterrows():
            summary.append(
                f"{row['Timestamp']} | {row['Ticker']} | "
                f"{row['Decision']} | Entry {row['Entry_Price']} | "
                f"Return {row.get('Return_%', 'NA')}% | Outcome {row['Outcome']}"
            )

summary.extend([
    "",
    "Market Preparation:",
    "EU_OPEN_WATCH",
    "US_OPEN_WATCH",
    "NO_AUTO_BUY",
    "NO_AUTO_SELL",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(summary)

Path("market_open_readiness_summary.txt").write_text(text)

print(text)
