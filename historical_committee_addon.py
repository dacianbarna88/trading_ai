from pathlib import Path

decision_file = Path("decision_accuracy_report.txt")
alignment_file = Path("historical_decision_alignment_summary.txt")

def extract(text, label):
    lines = text.splitlines()
    clean_label = label.replace(":", "").strip()

    for i, line in enumerate(lines):
        clean_line = line.replace(":", "").strip()

        if clean_line == clean_label:
            j = i + 1
            while j < len(lines):
                value = lines[j].strip()
                if value:
                    return value
                j += 1

        if line.startswith(label):
            return line.split(":", 1)[1].strip()

    return ""

decision_text = decision_file.read_text() if decision_file.exists() else ""
alignment_text = alignment_file.read_text() if alignment_file.exists() else ""

committee_edge = extract(decision_text, "Committee Edge").replace("%", "")
historical_edge = extract(alignment_text, "Historical Alignment Edge")

try:
    committee_edge_f = float(committee_edge)
except Exception:
    committee_edge_f = 0

try:
    historical_edge_f = float(historical_edge)
except Exception:
    historical_edge_f = 0

if committee_edge_f > 0 and historical_edge_f > 0:
    verdict = "STRONG_CONFIRMATION"
    confidence_boost = 10
elif committee_edge_f > 0 or historical_edge_f > 0:
    verdict = "PARTIAL_CONFIRMATION"
    confidence_boost = 5
else:
    verdict = "NO_CONFIRMATION"
    confidence_boost = 0

lines = [
    "===== V10.3 HISTORICAL COMMITTEE ADD-ON =====",
    "",
    f"Live Committee Edge: {committee_edge_f}%",
    f"Historical Alignment Edge: {historical_edge_f}",
    "",
    f"Historical Confirmation Verdict: {verdict}",
    f"Suggested Confidence Boost: {confidence_boost}%",
    "",
    "Interpretation:",
]

if verdict == "STRONG_CONFIRMATION":
    lines.append("Live decision accuracy and historical intelligence both support the committee decision.")
elif verdict == "PARTIAL_CONFIRMATION":
    lines.append("Only one of live accuracy or historical intelligence supports the committee decision.")
else:
    lines.append("Neither live accuracy nor historical intelligence currently supports the committee decision.")

lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(lines)
Path("historical_committee_addon_summary.txt").write_text(text)

print(text)
