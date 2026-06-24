import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

OUTPUT_FILE = "market_session_snapshots.csv"

allowed_sessions = [
    "MANUAL",
    "EU_OPEN",
    "EU_CLOSE",
    "US_PREMARKET",
    "US_OPEN",
    "US_CLOSE",
]

session = "MANUAL"

if len(sys.argv) > 1:
    session = sys.argv[1].upper()

if session not in allowed_sessions:
    print(f"Invalid session: {session}")
    print("Allowed sessions:")
    for s in allowed_sessions:
        print(f"- {s}")
    raise SystemExit

decision = "UNKNOWN"
confidence = 0

if Path("adaptive_decision_guard_summary.txt").exists():

    text = Path(
        "adaptive_decision_guard_summary.txt"
    ).read_text()

    for line in text.splitlines():

        if line.startswith("Guard Final Decision:"):
            decision = line.split(":", 1)[1].strip()

        if line.startswith("Weighted Confidence:"):
            raw = (
                line.split(":", 1)[1]
                .strip()
                .replace("%", "")
            )

            try:
                confidence = float(raw)
            except Exception:
                confidence = 0

record = {
    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "Session": session,
    "Decision": decision,
    "Confidence_%": confidence,
}

new_row = pd.DataFrame([record])

if Path(OUTPUT_FILE).exists():
    old = pd.read_csv(OUTPUT_FILE)
    df = pd.concat([old, new_row], ignore_index=True)
else:
    df = new_row

df.to_csv(OUTPUT_FILE, index=False)

print("===== V29.5 SESSION-AWARE SNAPSHOT =====")
print()
print(new_row.to_string(index=False))
print()
print(f"Total Snapshots: {len(df)}")
