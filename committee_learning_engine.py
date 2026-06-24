
import pandas as pd
from pathlib import Path
from datetime import datetime

committee_file = Path("strategic_committee_summary.txt")
accuracy_file = Path("decision_accuracy_report.txt")
action_file = Path("portfolio_action_summary.txt")
adaptive_file = Path("adaptive_strategic_risk_summary.txt")

if not committee_file.exists():
    raise SystemExit("strategic_committee_summary.txt not found")

committee_text = committee_file.read_text()
accuracy_text = accuracy_file.read_text() if accuracy_file.exists() else ""
action_text = action_file.read_text() if action_file.exists() else ""
adaptive_text = adaptive_file.read_text() if adaptive_file.exists() else ""

def extract(text, label):
    for line in text.splitlines():
        if line.startswith(label):
            return line.split(":", 1)[1].strip()
    return ""

row = {
    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

    "Committee_Vote": extract(committee_text, "Committee Vote"),
    "Confidence": extract(committee_text, "Confidence").replace("%", ""),
    "Committee_Score": extract(committee_text, "Committee Score"),

    "Committee_Edge": extract(accuracy_text, "Committee Edge").replace("%", ""),
    "Approved_Average": extract(accuracy_text, "Approved Average").replace("%", ""),
    "Rejected_Average": extract(accuracy_text, "Rejected Average").replace("%", ""),

    "Cash_Deployment": extract(action_text, "Suggested Cash Deployment").replace("%", ""),
    "Recommended_Action": extract(action_text, "Recommended Action"),
    "Risk_Stance": extract(action_text, "Risk Stance"),

    "Suggested_Risk": extract(adaptive_text, "Suggested Risk"),
    "Risk_Delta": extract(adaptive_text, "Risk Delta"),
    "Market_Regime": extract(adaptive_text, "Market Regime"),

    "High_Conflicts": extract(committee_text, "High Conflicts"),
    "Medium_Conflicts": extract(committee_text, "Medium Conflicts"),
    "Total_Conflicts": extract(committee_text, "Total Conflicts"),
}

csv_file = Path("committee_learning_history.csv")

if csv_file.exists():
    df = pd.read_csv(csv_file)
else:
    df = pd.DataFrame()

df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
df.to_csv(csv_file, index=False)

summary = f"""
===== COMMITTEE MEMORY EXPANSION V9.6 =====

Records Stored:
{len(df)}

Latest Vote:
{row['Committee_Vote']}

Latest Confidence:
{row['Confidence']}%

Latest Committee Edge:
{row['Committee_Edge']}%

Market Regime:
{row['Market_Regime']}

Suggested Risk:
{row['Suggested_Risk']}

High Conflicts:
{row['High_Conflicts']}

Medium Conflicts:
{row['Medium_Conflicts']}

Recommended Action:
{row['Recommended_Action']}

Risk Stance:
{row['Risk_Stance']}

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path("committee_learning_summary.txt").write_text(summary)
print(summary)
