from pathlib import Path

def read_file(path):
    if Path(path).exists():
        return Path(path).read_text()
    return ""

threshold_text = read_file(
    "threshold_intelligence_summary.txt"
)

market_text = read_file(
    "strategic_intelligence_summary.txt"
)

sector_text = read_file(
    "sector_intelligence_summary.txt"
)

horizon_text = read_file(
    "horizon_vote_summary.txt"
)

macro_text = read_file(
    "macro_committee_summary.txt"
)

votes = []

# Threshold Vote

if "KEEP_THRESHOLD_90" in threshold_text:
    votes.append(("THRESHOLD", "NEUTRAL"))
else:
    votes.append(("THRESHOLD", "BULLISH"))

# Regional Vote

if "OVERWEIGHT_US" in market_text:
    votes.append(("REGIONAL", "BULLISH_US"))
else:
    votes.append(("REGIONAL", "NEUTRAL"))

# Sector Vote

if "OVERWEIGHT_TECHNOLOGY" in sector_text:
    votes.append(("SECTOR", "BULLISH_TECH"))
else:
    votes.append(("SECTOR", "NEUTRAL"))

# Horizon Vote

if "LONG_TERM_US" in horizon_text:
    votes.append(("HORIZON", "LONG_TERM_US"))
elif "LONG_TERM_EUROPE" in horizon_text:
    votes.append(("HORIZON", "LONG_TERM_EUROPE"))
elif "LONG_TERM_UK" in horizon_text:
    votes.append(("HORIZON", "LONG_TERM_UK"))
else:
    votes.append(("HORIZON", "NEUTRAL"))

# Macro Vote

if "MACRO_BULLISH" in macro_text:
    votes.append(("MACRO", "MACRO_BULLISH"))
elif "MACRO_BEARISH" in macro_text:
    votes.append(("MACRO", "MACRO_BEARISH"))
else:
    votes.append(("MACRO", "NEUTRAL"))

bullish_votes = len([
    v for _, v in votes
    if v != "NEUTRAL"
])

confidence = round(
    bullish_votes / len(votes) * 100,
    1
)

if confidence >= 66:
    decision = "ACCUMULATE_US_TECH"
elif confidence >= 33:
    decision = "WATCHLIST_EXPANSION"
else:
    decision = "DEFENSIVE"

summary = [
    "===== V18.0 STRATEGIC COMMITTEE =====",
    "",
]

for name, vote in votes:
    summary.append(
        f"{name} Vote: {vote}"
    )

summary.extend([
    "",
    f"Confidence: {confidence}%",
    "",
    f"FINAL DECISION: {decision}",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(
    "strategic_committee_summary.txt"
).write_text(text)

print(text)
