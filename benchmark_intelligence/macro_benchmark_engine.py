from pathlib import Path

INPUT_FILE = "macro_committee_summary.txt"
OUTPUT_FILE = "macro_benchmark_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_MACRO_COMMITTEE")
    raise SystemExit

text = Path(INPUT_FILE).read_text()

if "MACRO_BULLISH" in text:
    macro_vote = "MACRO_BULLISH"
    benchmark = "SPY_POSITIVE_AFTER_90_DAYS"

elif "MACRO_BEARISH" in text:
    macro_vote = "MACRO_BEARISH"
    benchmark = "SPY_NEGATIVE_AFTER_90_DAYS"

else:
    macro_vote = "MACRO_NEUTRAL"
    benchmark = "MARKET_STABLE"

summary = f"""
===== V23.2 MACRO BENCHMARK ENGINE =====

Current Macro Vote:

{macro_vote}

Benchmark:

{benchmark}

Benchmark Status:

ACTIVE

Benchmark Rule:

Macro vote is CORRECT if market
performance matches the expected
macro direction after 90 days.

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
