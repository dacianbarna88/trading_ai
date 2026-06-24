from pathlib import Path

def read_text(file):
    if Path(file).exists():
        return Path(file).read_text()
    return ""

regime_text = read_text(
    "economic_regime_summary.txt"
)

rate_text = read_text(
    "rate_intelligence_summary.txt"
)

inflation_text = read_text(
    "inflation_intelligence_summary.txt"
)

votes = []

if "EXPANSION" in regime_text:
    votes.append(("REGIME", "BULLISH"))
elif "RECESSION_RISK" in regime_text:
    votes.append(("REGIME", "BEARISH"))
else:
    votes.append(("REGIME", "NEUTRAL"))

if "RATE_TAILWIND" in rate_text:
    votes.append(("RATES", "BULLISH"))
elif "RATE_HEADWIND" in rate_text:
    votes.append(("RATES", "BEARISH"))
else:
    votes.append(("RATES", "NEUTRAL"))

if "DISINFLATION" in inflation_text:
    votes.append(("INFLATION", "BULLISH"))
elif "INFLATION_PRESSURE" in inflation_text:
    votes.append(("INFLATION", "BEARISH"))
else:
    votes.append(("INFLATION", "NEUTRAL"))

bullish = len([v for _, v in votes if v == "BULLISH"])
bearish = len([v for _, v in votes if v == "BEARISH"])

if bullish > bearish:
    verdict = "MACRO_BULLISH"
elif bearish > bullish:
    verdict = "MACRO_BEARISH"
else:
    verdict = "MACRO_NEUTRAL"

confidence = round(
    max(bullish, bearish) / len(votes) * 100,
    1
)

summary = [
    "===== V19.4 MACRO COMMITTEE =====",
    ""
]

for name, vote in votes:
    summary.append(
        f"{name} Vote: {vote}"
    )

summary.extend([
    "",
    f"Confidence: {confidence}%",
    "",
    f"FINAL MACRO VOTE: {verdict}",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(
    "macro_committee_summary.txt"
).write_text(text)

print(text)
