import pandas as pd
from pathlib import Path

REGISTRY = "decision_registry.csv"
OUTPUT = "confidence_optimizer_summary.txt"

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY)

completed = df[
    df["Outcome"].isin(["WIN", "LOSS"])
]

summary = [
    "===== V31.7 CONFIDENCE OPTIMIZER ENGINE =====",
    "",
    f"Completed Decisions: {len(completed)}",
    "",
]

if len(completed) < 10:

    summary.extend([
        "Optimizer Status: INSUFFICIENT_HISTORY",
        "",
        "Reason:",
        "At least 10 completed WIN/LOSS decisions are needed before confidence optimization is reliable.",
        "",
        "Current Guidance:",
        "- Keep current confidence thresholds unchanged",
        "- Continue collecting decisions",
        "- Do not auto-adjust confidence gates yet",
    ])

else:

    bands = [
        ("80_PLUS", 80, 100),
        ("70_TO_79", 70, 79.999),
        ("60_TO_69", 60, 69.999),
        ("0_TO_59", 0, 59.999),
    ]

    best_band = None
    best_win_rate = -1

    summary.append("Confidence Band Performance:")
    summary.append("")

    for label, low, high in bands:

        band = completed[
            (completed["Confidence_%"] >= low)
            &
            (completed["Confidence_%"] <= high)
        ]

        total = len(band)
        wins = len(band[band["Outcome"] == "WIN"])
        losses = len(band[band["Outcome"] == "LOSS"])

        win_rate = round(wins / total * 100, 2) if total > 0 else 0
        avg_return = round(band["Return_%"].mean(), 2) if total > 0 and "Return_%" in band.columns else 0

        summary.append(label)
        summary.append(f"Total: {total}")
        summary.append(f"Wins: {wins}")
        summary.append(f"Losses: {losses}")
        summary.append(f"Win Rate: {win_rate}%")
        summary.append(f"Average Return: {avg_return}%")
        summary.append("")

        if total >= 3 and win_rate > best_win_rate:
            best_win_rate = win_rate
            best_band = label

    if best_band:
        summary.append(f"Best Confidence Band: {best_band}")
        summary.append(f"Best Win Rate: {best_win_rate}%")
    else:
        summary.append("Best Confidence Band: NOT_ENOUGH_BAND_DATA")

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(summary)

Path(OUTPUT).write_text(text)

print(text)
