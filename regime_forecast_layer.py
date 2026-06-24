from pathlib import Path

regime_file = Path("regime_intelligence_summary.txt")
confidence_file = Path("confidence_adjustment_summary.txt")
feedback_file = Path("learning_feedback_summary.txt")

def extract_value(text, label):
    lines = text.splitlines()
    clean_label = label.replace(":", "").strip()

    for i, line in enumerate(lines):
        line = line.strip()

        if line.startswith(label + ":"):
            value = line.split(":", 1)[1].strip()
            if value:
                return value

        clean_line = line.replace(":", "").strip()

        if clean_line == clean_label:
            j = i + 1
            while j < len(lines):
                value = lines[j].strip()
                if value:
                    return value
                j += 1

    return ""

regime_text = regime_file.read_text() if regime_file.exists() else ""
confidence_text = confidence_file.read_text() if confidence_file.exists() else ""
feedback_text = feedback_file.read_text() if feedback_file.exists() else ""

market_regime = extract_value(regime_text, "Current Market Regime")
profile = extract_value(regime_text, "Regime Profile")
dominant_horizon = extract_value(regime_text, "Dominant Horizon")
adjusted_confidence = extract_value(confidence_text, "Adjusted Confidence")
lesson = extract_value(feedback_text, "Learning Lesson")

try:
    adjusted_conf = float(adjusted_confidence.replace("%", ""))
except Exception:
    adjusted_conf = 0

forecast = "NEUTRAL"
stance = "CAUTIOUS"
risk_bias = "NORMAL"

if market_regime == "BULL" and profile == "SUPER_CYCLE" and adjusted_conf >= 70:
    forecast = "BULL_CONTINUATION"
    stance = "SELECTIVE_GROWTH"
    risk_bias = "MODERATE_POSITIVE"

if lesson == "REJECTION_TOO_STRICT":
    stance = "SELECTIVE_GROWTH_WITH_REVIEW"
    risk_bias = "MODERATE_POSITIVE_BUT_WATCH_REJECTS"

lines = [
    "===== V12.1 REGIME FORECAST LAYER =====",
    "",
    f"Market Regime: {market_regime}",
    f"Regime Profile: {profile}",
    f"Dominant Horizon: {dominant_horizon}",
    f"Adjusted Confidence: {adjusted_conf}%",
    f"Learning Lesson: {lesson}",
    "",
    f"Forecast: {forecast}",
    f"Strategic Stance: {stance}",
    f"Risk Bias: {risk_bias}",
    "",
    "Interpretation:",
]

if forecast == "BULL_CONTINUATION":
    lines.append("Historical structure and adjusted confidence support continued selective exposure.")
else:
    lines.append("Forecast remains neutral until more confirmation is available.")

lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(lines)
Path("regime_forecast_summary.txt").write_text(text)
print(text)
