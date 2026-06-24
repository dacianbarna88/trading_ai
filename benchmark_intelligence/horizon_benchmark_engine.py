from pathlib import Path

INPUT_FILE = "horizon_vote_summary.txt"
OUTPUT_FILE = "horizon_benchmark_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_HORIZON_VOTE")
    raise SystemExit

text = Path(INPUT_FILE).read_text()

if "LONG_TERM_US" in text:
    horizon_vote = "LONG_TERM_US"
    benchmark = "US_OUTPERFORMS_GLOBAL_PEERS_AFTER_180_DAYS"
elif "LONG_TERM_EUROPE" in text:
    horizon_vote = "LONG_TERM_EUROPE"
    benchmark = "EUROPE_OUTPERFORMS_GLOBAL_PEERS_AFTER_180_DAYS"
elif "LONG_TERM_UK" in text:
    horizon_vote = "LONG_TERM_UK"
    benchmark = "UK_OUTPERFORMS_GLOBAL_PEERS_AFTER_180_DAYS"
else:
    horizon_vote = "HORIZON_NEUTRAL"
    benchmark = "NO_LONG_TERM_DIRECTION_REQUIRED"

summary = f"""
===== V23.3 HORIZON BENCHMARK ENGINE =====

Current Horizon Vote:

{horizon_vote}

Benchmark:

{benchmark}

Benchmark Status:

ACTIVE

Benchmark Rule:

Horizon vote is CORRECT if the selected
long-term region outperforms its global
peers after the horizon validation period.

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
