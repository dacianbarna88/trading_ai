import pandas as pd
from pathlib import Path
from datetime import datetime

memory_file = "learning_memory.csv"
scoreboard_file = "learning_scoreboard.csv"

if not Path(memory_file).exists():
    raise SystemExit("learning_memory.csv not found")

df = pd.read_csv(memory_file)

today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

post = df[df["Source"] == "post_sell"]
rebalance = df[df["Source"] == "rebalance"]
missed = df[df["Source"] == "missed_winners"]
threshold = df[df["Source"] == "threshold"]

# SELL QUALITY
sell_quality = 0
if not post.empty and "Verdict" in post.columns:
    good_like = post[
        post["Verdict"].isin(["GOOD_SELL", "ACCEPTABLE_SELL"])
    ]
    sell_quality = round(len(good_like) / len(post) * 100, 2)

# REBALANCE EDGE
rebalance_edge = 0
if not rebalance.empty and "Verdict" in rebalance.columns:
    good = len(rebalance[rebalance["Verdict"] == "GOOD_REBALANCE"])
    bad = len(rebalance[rebalance["Verdict"] == "BAD_REBALANCE"])
    rebalance_edge = round((good - bad) / len(rebalance) * 100, 2)

# MISSED WINNER RATE
missed_winner_rate = 0
if not missed.empty and "Verdict" in missed.columns:
    missed_count = len(
        missed[
            missed["Verdict"].isin([
                "MISSED_BY_SCORE",
                "POTENTIAL_MISSED_WINNER"
            ])
        ]
    )
    missed_winner_rate = round(missed_count / len(missed) * 100, 2)

# THRESHOLD OPPORTUNITY
threshold_90_candidates = 0
threshold_80_candidates = 0

if not threshold.empty:
    t90 = threshold[threshold["Threshold"] == 90]
    t80 = threshold[threshold["Threshold"] == 80]

    if not t90.empty:
        threshold_90_candidates = int(t90.iloc[-1]["Candidates"])

    if not t80.empty:
        threshold_80_candidates = int(t80.iloc[-1]["Candidates"])

threshold_opportunity = threshold_80_candidates - threshold_90_candidates

row = {
    "Timestamp": today,
    "Learning_Records": len(df),
    "Sell_Quality_%": sell_quality,
    "Rebalance_Edge_%": rebalance_edge,
    "Missed_Winner_Rate_%": missed_winner_rate,
    "Threshold_90_Candidates": threshold_90_candidates,
    "Threshold_80_Candidates": threshold_80_candidates,
    "Threshold_Opportunity": threshold_opportunity,
    "Mode": "AUDIT_ONLY",
}

score = pd.DataFrame([row])

if Path(scoreboard_file).exists():
    old = pd.read_csv(scoreboard_file)
    score = pd.concat([old, score], ignore_index=True)

score.to_csv(scoreboard_file, index=False)

summary = f"""
===== V14.2 LEARNING SCOREBOARD =====

Learning Records:
{len(df)}

Sell Quality:
{sell_quality}%

Rebalance Edge:
{rebalance_edge}%

Missed Winner Rate:
{missed_winner_rate}%

Threshold 90 Candidates:
{threshold_90_candidates}

Threshold 80 Candidates:
{threshold_80_candidates}

Threshold Opportunity:
+{threshold_opportunity} candidates

Mode:
AUDIT_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path("learning_scoreboard_summary.txt").write_text(summary)

print(summary)
print(score.tail(10).to_string(index=False))
