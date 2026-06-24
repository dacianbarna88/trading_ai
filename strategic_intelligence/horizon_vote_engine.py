from pathlib import Path

FILES = [
    "horizon_validation_summary.txt",
    "adaptive_allocation_summary.txt",
    "strategic_horizon_summary.txt",
]

texts = []

for f in FILES:
    if Path(f).exists():
        texts.append(Path(f).read_text())

combined = "\n".join(texts)

if not combined.strip():
    vote = "MISSING_HORIZON_DATA"
    confidence = 0
elif "Consensus Leader: US" in combined or "Long-Term Bias: US" in combined:
    vote = "LONG_TERM_US"
    confidence = 75
elif "Consensus Leader: EU" in combined or "Long-Term Bias: EU" in combined:
    vote = "LONG_TERM_EUROPE"
    confidence = 65
elif "Consensus Leader: UK" in combined or "Long-Term Bias: UK" in combined:
    vote = "LONG_TERM_UK"
    confidence = 60
else:
    vote = "HORIZON_NEUTRAL"
    confidence = 50

summary = f"""
===== V18.1 HORIZON VOTE ENGINE =====

Horizon Vote:
{vote}

Confidence:
{confidence}%

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path("horizon_vote_summary.txt").write_text(summary)

print(summary)
