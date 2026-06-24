from pathlib import Path
import pandas as pd

OUTPUT = "learning_health_summary.txt"

score = 0

# 1. Learning history health — 25p
history_score = 0
if Path("learning_weight_history.csv").exists():
    hist = pd.read_csv("learning_weight_history.csv")
    history_score += 10

    if len(hist) >= 5:
        history_score += 5

    completed = hist[hist["Outcome"].isin(["WIN", "LOSS"])]
    if len(completed) > 0:
        history_score += 10

score += history_score

# 2. Decision registry health — 25p
registry_score = 0
if Path("decision_registry.csv").exists():
    reg = pd.read_csv("decision_registry.csv")
    registry_score += 10

    if len(reg) >= 1:
        registry_score += 5

    completed_reg = reg[reg["Outcome"].isin(["WIN", "LOSS"])]
    if len(completed_reg) > 0:
        registry_score += 10

score += registry_score

# 3. Adaptive weights health — 25p
weights_score = 0
if Path("adaptive_weights.csv").exists():
    weights = pd.read_csv("adaptive_weights.csv")
    weights_score += 10

    if "New_Weight" in weights.columns:
        weights_score += 5

    unique_weights = weights["New_Weight"].nunique() if "New_Weight" in weights.columns else 0
    if unique_weights > 1:
        weights_score += 10

score += weights_score

# 4. Analytics health — 25p
analytics_score = 0
analytics_files = [
    "decision_quality_summary.txt",
    "confidence_calibration_summary.txt",
    "outcome_analytics_summary.txt",
    "market_readiness_score_summary.txt",
]

for f in analytics_files:
    if Path(f).exists():
        analytics_score += 6

if analytics_score > 25:
    analytics_score = 25

score += analytics_score

if score >= 80:
    status = "HEALTHY"
elif score >= 60:
    status = "DEVELOPING"
elif score >= 40:
    status = "LIMITED"
else:
    status = "WEAK"

summary = f"""
===== V30.6 LEARNING HEALTH ENGINE =====

Learning History Score: {history_score}/25
Decision Registry Score: {registry_score}/25
Adaptive Weights Score: {weights_score}/25
Analytics Score: {analytics_score}/25

Learning Health Score: {score}/100

Learning Status: {status}

Interpretation:
Infrastructure is active.
Real learning quality depends on completed WIN/LOSS outcomes.

Mode:
ANALYSIS_ONLY
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path(OUTPUT).write_text(summary)

print(summary)
