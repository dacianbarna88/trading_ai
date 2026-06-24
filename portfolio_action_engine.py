from pathlib import Path


def read_text(path):
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text()


def extract_value(text, label, default="UNKNOWN"):
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if line.startswith(label):
            value = line.split(":", 1)[1].strip() if ":" in line else ""

            if value:
                return value

            if i + 1 < len(lines):
                return lines[i + 1].strip()

    return default


def extract_float(text, label, default=0.0):
    value = extract_value(text, label, str(default))

    try:
        return float(value.replace("%", ""))
    except Exception:
        return default


committee = read_text("strategic_committee_summary.txt")
confidence_engine = read_text("committee_confidence_breakdown.txt")

vote = extract_value(committee, "Committee Vote", "UNKNOWN")
confidence = extract_float(committee, "Confidence", 0)
suggested_risk = extract_float(confidence_engine, "Suggested Risk", 0)
high_conflicts = extract_float(confidence_engine, "High Conflicts", 0)
medium_conflicts = extract_float(confidence_engine, "Medium Conflicts", 0)
net_score = extract_float(confidence_engine, "Net Committee Score", 0)

recommended_action = "HOLD"
cash_deployment_pct = 0
risk_stance = "NEUTRAL"
reason = "No actionable committee signal."

if vote == "AGGRESSIVE":
    recommended_action = "EXPAND_POSITIONS"
    cash_deployment_pct = 50
    risk_stance = "RISK_ON"
    reason = "Committee supports expansion with strong confidence."

elif vote == "NORMAL":
    recommended_action = "SELECTIVE_BUY"
    cash_deployment_pct = 35
    risk_stance = "BALANCED"
    reason = "Committee supports selective exposure."

elif vote == "CAUTIOUS":
    recommended_action = "SELECTIVE_BUY_REDUCED_SIZE"
    cash_deployment_pct = 20
    risk_stance = "CAUTIOUS"
    reason = "Positive risk signals are offset by strategic conflicts."

elif vote == "DEFENSIVE":
    recommended_action = "HOLD_OR_REDUCE_RISK"
    cash_deployment_pct = 0
    risk_stance = "DEFENSIVE"
    reason = "Committee recommends preserving capital."

if high_conflicts >= 1:
    cash_deployment_pct = min(cash_deployment_pct, 20)
    reason += " High conflicts cap cash deployment."

if medium_conflicts >= 5:
    cash_deployment_pct = min(cash_deployment_pct, 20)
    reason += " Multiple medium conflicts require caution."

if confidence < 60:
    cash_deployment_pct = min(cash_deployment_pct, 10)
    reason += " Confidence below 60% limits exposure."

lines = [
    "===== PORTFOLIO ACTION ENGINE =====",
    "",
    f"Committee Vote: {vote}",
    f"Confidence: {confidence}%",
    f"Net Committee Score: {net_score}",
    "",
    f"Suggested Risk: {suggested_risk}",
    f"High Conflicts: {int(high_conflicts)}",
    f"Medium Conflicts: {int(medium_conflicts)}",
    "",
    f"Recommended Action: {recommended_action}",
    f"Suggested Cash Deployment: {cash_deployment_pct}%",
    f"Risk Stance: {risk_stance}",
    "",
    f"Reason: {reason}",
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
]

text = "\n".join(lines)

Path("portfolio_action_summary.txt").write_text(text)

print(text)
