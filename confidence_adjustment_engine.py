from pathlib import Path

feedback_file = Path("learning_feedback_summary.txt")
committee_file = Path("strategic_committee_summary.txt")
addon_file = Path("historical_committee_addon_summary.txt")

def extract(text, label):
    for line in text.splitlines():
        if line.startswith(label):
            return line.split(":", 1)[1].strip()
    return ""

feedback_text = feedback_file.read_text() if feedback_file.exists() else ""
committee_text = committee_file.read_text() if committee_file.exists() else ""
addon_text = addon_file.read_text() if addon_file.exists() else ""

lesson = extract(feedback_text, "Learning Lesson")
base_conf = extract(committee_text, "Confidence").replace("%", "")
boost = extract(addon_text, "Suggested Confidence Boost").replace("%", "")

try:
    base_conf = float(base_conf)
except Exception:
    base_conf = 0

try:
    boost = float(boost)
except Exception:
    boost = 0

penalty = 0

if lesson == "REJECTION_TOO_STRICT":
    penalty = 5
elif lesson == "COMMITTEE_SELECTION_CONFIRMED":
    penalty = 0
else:
    penalty = 0

adjusted_confidence = base_conf + boost - penalty
adjusted_confidence = max(0, min(100, adjusted_confidence))

lines = [
    "===== V11.3 CONFIDENCE ADJUSTMENT ENGINE =====",
    "",
    f"Base Committee Confidence: {base_conf}%",
    f"Historical Confidence Boost: {boost}%",
    f"Learning Penalty: -{penalty}%",
    "",
    f"Adjusted Confidence: {adjusted_confidence}%",
    "",
    f"Learning Lesson: {lesson}",
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
]

text = "\n".join(lines)

Path("confidence_adjustment_summary.txt").write_text(text)

print(text)
