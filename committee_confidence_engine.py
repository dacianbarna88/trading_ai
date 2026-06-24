from pathlib import Path


def read_text(path):
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text()


def extract_float(text, label, default=0.0):
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if line.startswith(label):
            value = line.split(":", 1)[1].strip() if ":" in line else ""

            if value:
                try:
                    return float(value)
                except Exception:
                    return default

            if i + 1 < len(lines):
                try:
                    return float(lines[i + 1].strip())
                except Exception:
                    return default

    return default


def count_occurrences(text, phrase):
    return text.count(phrase)


adaptive_risk = read_text("adaptive_strategic_risk_summary.txt")
conflicts = read_text("strategic_conflict_summary.txt")
sizing = read_text("conflict_position_sizing_summary.txt")
rebalance = read_text("strategic_rebalance_summary.txt")
committee = read_text("strategic_committee_summary.txt")

suggested_risk = extract_float(adaptive_risk, "Suggested Risk")
risk_delta = extract_float(adaptive_risk, "Risk Delta")
projected_score = extract_float(rebalance, "Projected Strategic Score")
projected_health = extract_float(rebalance, "Projected Allocator Health")
alignment_before = extract_float(rebalance, "Alignment Before")

high_conflicts = count_occurrences(conflicts, "Conflict HIGH")
medium_conflicts = count_occurrences(conflicts, "Conflict MEDIUM")
size_50 = count_occurrences(sizing, "Suggested Size 50%")
size_75 = count_occurrences(sizing, "Suggested Size 75%")

risk_contribution = 0
rebalance_contribution = 0
conflict_contribution = 0
sizing_contribution = 0
allocation_contribution = 0

if suggested_risk >= 0.6:
    risk_contribution += 2

if risk_delta > 0:
    risk_contribution += 1

if projected_score >= 50:
    rebalance_contribution += 1

if projected_health >= 50:
    rebalance_contribution += 1

if alignment_before < 85:
    allocation_contribution -= 1

if high_conflicts >= 1:
    conflict_contribution -= 2

if medium_conflicts >= 5:
    conflict_contribution -= 1

if size_50 >= 1:
    sizing_contribution -= 1

net_score = (
    risk_contribution
    + rebalance_contribution
    + allocation_contribution
    + conflict_contribution
    + sizing_contribution
)

if net_score >= 4:
    vote = "AGGRESSIVE"
elif net_score >= 2:
    vote = "NORMAL"
elif net_score >= 0:
    vote = "CAUTIOUS"
else:
    vote = "DEFENSIVE"

confidence = min(95, max(50, 65 + abs(net_score) * 5))

lines = [
    "===== COMMITTEE CONFIDENCE ENGINE =====",
    "",
    f"Risk Engine Contribution: {risk_contribution}",
    f"Rebalance Engine Contribution: {rebalance_contribution}",
    f"Allocation Engine Contribution: {allocation_contribution}",
    f"Conflict Engine Contribution: {conflict_contribution}",
    f"Position Sizing Contribution: {sizing_contribution}",
    "",
    f"Net Committee Score: {net_score}",
    f"Committee Vote: {vote}",
    f"Confidence: {confidence}%",
    "",
    "Inputs:",
    f"Suggested Risk: {suggested_risk}",
    f"Risk Delta: {risk_delta}",
    f"Projected Strategic Score: {projected_score}",
    f"Projected Allocator Health: {projected_health}",
    f"Alignment Before: {alignment_before}",
    f"High Conflicts: {high_conflicts}",
    f"Medium Conflicts: {medium_conflicts}",
    f"50% Size Adjustments: {size_50}",
    f"75% Size Adjustments: {size_75}",
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
]

text = "\n".join(lines)

Path("committee_confidence_breakdown.txt").write_text(text)

print(text)
