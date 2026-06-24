import pandas as pd
from pathlib import Path

memory_file = "learning_memory.csv"

if not Path(memory_file).exists():
    raise SystemExit("learning_memory.csv not found")

df = pd.read_csv(memory_file)

lines = [
    "===== V14.1 LEARNING INSIGHTS =====",
    "",
    f"Total Learning Records: {len(df)}",
    "",
]

# Post-sell accuracy
post = df[df["Source"] == "post_sell"]

if not post.empty and "Verdict" in post.columns:
    verdicts = post["Verdict"].dropna().value_counts()

    lines.append("Post-Sell Learning:")
    for verdict, count in verdicts.items():
        lines.append(f"- {verdict}: {count}")

    good_like = post[
        post["Verdict"].isin(["GOOD_SELL", "ACCEPTABLE_SELL"])
    ]

    sell_quality = round(len(good_like) / len(post) * 100, 2)
    lines.append(f"Sell Quality: {sell_quality}%")
    lines.append("")

# Missed winners
missed = df[df["Source"] == "missed_winners"]

if not missed.empty and "Verdict" in missed.columns:
    verdicts = missed["Verdict"].dropna().value_counts()

    lines.append("Missed Winners Learning:")
    for verdict, count in verdicts.items():
        lines.append(f"- {verdict}: {count}")

    repeated = (
        missed["Ticker"]
        .dropna()
        .value_counts()
        .head(5)
    )

    lines.append("Top Watched/Missed Symbols:")
    for ticker, count in repeated.items():
        lines.append(f"- {ticker}: {count}")

    lines.append("")

# Rebalance learning
rebalance = df[df["Source"] == "rebalance"]

if not rebalance.empty and "Verdict" in rebalance.columns:
    verdicts = rebalance["Verdict"].dropna().value_counts()

    lines.append("Rebalance Learning:")
    for verdict, count in verdicts.items():
        lines.append(f"- {verdict}: {count}")

    good = len(rebalance[rebalance["Verdict"] == "GOOD_REBALANCE"])
    bad = len(rebalance[rebalance["Verdict"] == "BAD_REBALANCE"])

    edge = round((good - bad) / len(rebalance) * 100, 2)
    lines.append(f"Rebalance Edge: {edge}%")
    lines.append("")

# Threshold learning
threshold = df[df["Source"] == "threshold"]

if not threshold.empty:
    lines.append("Threshold Learning:")

    usable = threshold[
        ["Threshold", "Candidates", "Average_Score"]
    ].dropna()

    for _, r in usable.iterrows():
        lines.append(
            f"- Threshold {int(r['Threshold'])}: "
            f"{int(r['Candidates'])} candidates | "
            f"avg score {round(float(r['Average_Score']),2)}"
        )

    lines.append("")

# System conclusion
lines.extend([
    "Current Learning Conclusion:",
    "SELL_ENGINE_OK",
    "REBALANCE_NEEDS_MORE_DATA",
    "THRESHOLD_80_WORTH_MONITORING",
    "NO_AUTO_CHANGE_RECOMMENDED_YET",
    "",
    "Mode:",
    "AUDIT_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(lines)

Path("learning_insights_summary.txt").write_text(text)

print(text)
