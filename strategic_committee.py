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
            after_colon = line.split(":", 1)[1].strip() if ":" in line else ""

            if after_colon:
                try:
                    return float(after_colon)
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

suggested_risk = extract_float(adaptive_risk, "Suggested Risk")
risk_delta = extract_float(adaptive_risk, "Risk Delta")
alignment_before = extract_float(rebalance, "Alignment Before")
projected_score = extract_float(rebalance, "Projected Strategic Score")
projected_health = extract_float(rebalance, "Projected Allocator Health")

high_conflicts = count_occurrences(conflicts, "Conflict HIGH")
medium_conflicts = count_occurrences(conflicts, "Conflict MEDIUM")
total_conflicts = high_conflicts + medium_conflicts

size_50 = count_occurrences(sizing, "Suggested Size 50%")
size_75 = count_occurrences(sizing, "Suggested Size 75%")

score = 0
reasons = []

if suggested_risk >= 0.6:
    score += 2
    reasons.append("Adaptive risk supports higher exposure")

if risk_delta > 0:
    score += 1
    reasons.append("Risk delta is positive")

if projected_score >= 50:
    score += 1
    reasons.append("Projected strategic score improves above 50")

if projected_health >= 50:
    score += 1
    reasons.append("Projected allocator health improves above 50")

if alignment_before < 85:
    score -= 1
    reasons.append("Allocation alignment is not yet optimal")

if high_conflicts >= 1:
    score -= 2
    reasons.append("High strategic conflicts detected")

if medium_conflicts >= 5:
    score -= 1
    reasons.append("Multiple medium conflicts detected")

if size_50 >= 1:
    score -= 1
    reasons.append("At least one position requires 50% sizing")

if score >= 4:
    vote = "AGGRESSIVE"
elif score >= 2:
    vote = "NORMAL"
elif score >= 0:
    vote = "CAUTIOUS"
else:
    vote = "DEFENSIVE"

confidence = min(95, max(50, 65 + abs(score) * 5))

summary = [
    "===== STRATEGIC COMMITTEE =====",
    "",
    f"Suggested Risk: {suggested_risk}",
    f"Risk Delta: {risk_delta}",
    "",
    f"Projected Strategic Score: {projected_score}",
    f"Projected Allocator Health: {projected_health}",
    f"Allocation Alignment Before: {alignment_before}",
    "",
    f"High Conflicts: {high_conflicts}",
    f"Medium Conflicts: {medium_conflicts}",
    f"Total Conflicts: {total_conflicts}",
    "",
    f"50% Size Adjustments: {size_50}",
    f"75% Size Adjustments: {size_75}",
    "",
    f"Committee Score: {score}",
    f"Committee Vote: {vote}",
    f"Confidence: {confidence}%",
    "",
    "Reasons:",
]

for reason in reasons:
    summary.append(f"- {reason}")

summary.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(summary)

Path("strategic_committee_summary.txt").write_text(text)

print(text)
