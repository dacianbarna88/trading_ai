import pandas as pd
from pathlib import Path

REGISTRY = "decision_registry.csv"
WEIGHTS = "adaptive_weights.csv"
OUTPUT = "learning_recommendations_engine_summary.txt"

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

if not Path(WEIGHTS).exists():
    print("adaptive_weights.csv missing")
    raise SystemExit

registry = pd.read_csv(REGISTRY)
weights = pd.read_csv(WEIGHTS)

completed = registry[
    registry["Outcome"].isin(["WIN", "LOSS"])
]

summary = [
    "===== V31.5 LEARNING RECOMMENDATIONS ENGINE =====",
    "",
    f"Completed Decisions: {len(completed)}",
    "",
]

if len(completed) < 5:

    summary.extend([
        "Recommendation Status: INSUFFICIENT_HISTORY",
        "",
        "Reason:",
        "At least 5 completed WIN/LOSS outcomes are needed before learning recommendations are reliable.",
        "",
        "Current Recommendations:",
        "- Keep PAPER_ONLY mode active",
        "- Do not change adaptive weights automatically",
        "- Continue collecting EU_OPEN and US_OPEN snapshots",
        "- Continue tracking decision outcomes",
    ])

else:

    win_rate = round(
        len(completed[completed["Outcome"] == "WIN"]) / len(completed) * 100,
        2
    )

    avg_return = round(
        completed["Return_%"].mean(),
        2
    ) if "Return_%" in completed.columns else 0

    summary.append(f"Overall Win Rate: {win_rate}%")
    summary.append(f"Average Return: {avg_return}%")
    summary.append("")
    summary.append("Recommendations:")

    if win_rate >= 65:
        summary.append("- Current decision framework is performing well")
        summary.append("- Keep adaptive weight logic unchanged")
    elif win_rate >= 50:
        summary.append("- Performance is acceptable but not strong")
        summary.append("- Keep Conflict Guard active")
        summary.append("- Avoid increasing exposure")
    else:
        summary.append("- Performance is weak")
        summary.append("- Reduce aggressive BUY interpretation")
        summary.append("- Increase caution on CONTROLLED_BUY decisions")

    if avg_return < 0:
        summary.append("- Average return is negative; review stop/target settings")

    summary.append("")
    summary.append("Current Adaptive Weights:")

    for _, row in weights.iterrows():
        summary.append(
            f"- {row['Vote']}: {row['New_Weight']}"
        )

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
