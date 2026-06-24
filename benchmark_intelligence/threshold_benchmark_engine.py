from pathlib import Path

INPUT_FILE = "threshold_intelligence_summary.txt"
OUTPUT_FILE = "threshold_benchmark_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_THRESHOLD_INTELLIGENCE")
    raise SystemExit

text = Path(INPUT_FILE).read_text()

if "KEEP_THRESHOLD_90" in text:
    threshold_vote = "KEEP_THRESHOLD_90"
    benchmark = "THRESHOLD_80_DOES_NOT_OUTPERFORM_THRESHOLD_90"
elif "CONSIDER_THRESHOLD_80" in text:
    threshold_vote = "CONSIDER_THRESHOLD_80"
    benchmark = "THRESHOLD_80_OUTPERFORMS_THRESHOLD_90"
else:
    threshold_vote = "THRESHOLD_NEUTRAL"
    benchmark = "NO_THRESHOLD_DIRECTION_REQUIRED"

summary = f"""
===== V23.4 THRESHOLD BENCHMARK ENGINE =====

Current Threshold Vote:

{threshold_vote}

Benchmark:

{benchmark}

Benchmark Status:

ACTIVE

Benchmark Rule:

Threshold vote is CORRECT if the
observed virtual threshold outcome
matches the threshold decision after
the validation period.

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
