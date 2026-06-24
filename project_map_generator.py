from pathlib import Path
from datetime import datetime

OUTPUT = "PROJECT_MAP.md"

sections = {
    "Core Daily Runner": [
        "daily_intelligence_runner.py",
    ],
    "Decision Registry & Outcome": [
        "decision_registry.py",
        "enrich_decision_registry.py",
        "entry_price_filler.py",
        "outcome_assignment_engine.py",
        "outcome_evaluator.py",
        "feedback_update_engine.py",
    ],
    "Learning & Intelligence": [
        "decision_quality_engine.py",
        "confidence_calibration_engine.py",
        "outcome_analytics_engine.py",
        "learning_health_engine.py",
        "master_intelligence_score.py",
    ],
    "Self-Learning Engines": [
        "decision_replay_engine.py",
        "pattern_discovery_engine.py",
        "learning_recommendations_engine.py",
        "confidence_optimizer_engine.py",
    ],
    "Market & Session Intelligence": [
        "market_open_readiness.py",
        "market_session_snapshot.py",
        "session_intelligence_engine.py",
        "market_readiness_score.py",
    ],
    "Dashboard": [
        "dashboard_v2.py",
    ],
    "Key Data Files": [
        "decision_registry.csv",
        "market_session_snapshots.csv",
        "learning_weight_history.csv",
        "adaptive_weights.csv",
    ],
    "Key Reports": [
        "daily_intelligence_report.txt",
        "master_intelligence_score_summary.txt",
        "learning_health_summary.txt",
        "market_readiness_score_summary.txt",
        "decision_replay_summary.txt",
        "pattern_discovery_summary.txt",
        "learning_recommendations_engine_summary.txt",
        "confidence_optimizer_summary.txt",
    ],
}

lines = []

lines.append("# Trading AI Project Map")
lines.append("")
lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
lines.append("")
lines.append("## Current Architecture")
lines.append("")
lines.append("```text")
lines.append("Strategic Committee")
lines.append("  ↓")
lines.append("Adaptive Weights")
lines.append("  ↓")
lines.append("Weighted Decision")
lines.append("  ↓")
lines.append("Conflict Guard")
lines.append("  ↓")
lines.append("Decision Registry")
lines.append("  ↓")
lines.append("Outcome Evaluator")
lines.append("  ↓")
lines.append("Feedback Update")
lines.append("  ↓")
lines.append("Replay / Pattern Discovery")
lines.append("  ↓")
lines.append("Recommendations / Confidence Optimizer")
lines.append("  ↓")
lines.append("Master Intelligence Score")
lines.append("```")
lines.append("")

for title, files in sections.items():
    lines.append(f"## {title}")
    lines.append("")

    for file in files:
        exists = "OK" if Path(file).exists() else "MISSING"
        lines.append(f"- `{file}` — {exists}")

    lines.append("")

lines.append("## Current Mode")
lines.append("")
lines.append("```text")
lines.append("ANALYSIS_ONLY")
lines.append("PAPER_ONLY")
lines.append("NO_BROKER")
lines.append("NO_AUTO_EXECUTION")
lines.append("```")
lines.append("")
lines.append("## Operational Command")
lines.append("")
lines.append("```bash")
lines.append("python3 daily_intelligence_runner.py")
lines.append("```")
lines.append("")
lines.append("## Notes")
lines.append("")
lines.append("- The system is structurally ready.")
lines.append("- The main limitation is insufficient completed WIN/LOSS outcomes.")
lines.append("- Do not enable broker execution until the platform has enough validated history.")

Path(OUTPUT).write_text("\n".join(lines))

print("===== V32.3 PROJECT MAP GENERATED =====")
print(f"Output: {OUTPUT}")
