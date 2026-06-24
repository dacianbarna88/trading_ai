from pathlib import Path
from datetime import datetime
import pandas as pd

SIGNALS = "live_signals.csv"
REGISTRY = "decision_registry.csv"
SUMMARY = "signal_to_decision_summary.txt"

MIN_SCORE = 90
DEFAULT_EVAL_DAYS = 5
DEFAULT_TARGET = 2.0
DEFAULT_STOP = -2.0

registry_columns = [
    "Timestamp",
    "Decision",
    "Confidence_%",
    "Outcome",
    "Mode",
    "Ticker",
    "Entry_Price",
    "Evaluation_Days",
    "Target_Return_%",
    "Stop_Return_%",
    "Current_Price",
    "Return_%",
]

if not Path(SIGNALS).exists():
    print("live_signals.csv missing")
    raise SystemExit

signals = pd.read_csv(SIGNALS)

if Path(REGISTRY).exists():
    registry = pd.read_csv(REGISTRY)
else:
    registry = pd.DataFrame(columns=registry_columns)

for col in registry_columns:
    if col not in registry.columns:
        registry[col] = None

registry = registry[registry_columns]

candidates = signals[
    (signals["Signal"].astype(str) == "STRONG BUY")
    &
    (signals["Score"].astype(float) >= MIN_SCORE)
].copy()

added = 0
skipped = 0

details = []

for _, row in candidates.iterrows():

    ticker = str(row["Ticker"]).strip()
    price = float(row["Price"])
    score = float(row["Score"])

    existing_pending = registry[
        (registry["Ticker"].astype(str) == ticker)
        &
        (registry["Outcome"].astype(str) == "PENDING")
    ]

    if len(existing_pending) > 0:
        skipped += 1
        details.append(f"{ticker} skipped - already pending")
        continue

    confidence = min(95.0, round(score * 0.9, 2))

    registry.loc[len(registry)] = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "CONTROLLED_BUY",
        confidence,
        "PENDING",
        "PAPER_ONLY",
        ticker,
        price,
        DEFAULT_EVAL_DAYS,
        DEFAULT_TARGET,
        DEFAULT_STOP,
        price,
        0.0,
    ]

    added += 1
    details.append(
        f"{ticker} added | Score {score} | Confidence {confidence}% | Entry {price}"
    )

registry.to_csv(REGISTRY, index=False)

summary = [
    "===== V35.0 SIGNAL TO DECISION ENGINE =====",
    "",
    f"Candidates Found: {len(candidates)}",
    f"Decisions Added: {added}",
    f"Decisions Skipped: {skipped}",
    "",
    "Details:",
]

summary.extend(details if details else ["No candidates processed."])

summary.extend([
    "",
    "Rules:",
    f"Signal = STRONG BUY",
    f"Score >= {MIN_SCORE}",
    "Decision = CONTROLLED_BUY",
    "",
    "Mode:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(summary)

Path(SUMMARY).write_text(text)

print(text)
