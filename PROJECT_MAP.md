# Trading AI Project Map

Generated: 2026-06-21 16:00:24

## Current Architecture

```text
Strategic Committee
  ↓
Adaptive Weights
  ↓
Weighted Decision
  ↓
Conflict Guard
  ↓
Decision Registry
  ↓
Outcome Evaluator
  ↓
Feedback Update
  ↓
Replay / Pattern Discovery
  ↓
Recommendations / Confidence Optimizer
  ↓
Master Intelligence Score
```

## Core Daily Runner

- `daily_intelligence_runner.py` — OK

## Decision Registry & Outcome

- `decision_registry.py` — OK
- `enrich_decision_registry.py` — OK
- `entry_price_filler.py` — OK
- `outcome_assignment_engine.py` — OK
- `outcome_evaluator.py` — OK
- `feedback_update_engine.py` — OK

## Learning & Intelligence

- `decision_quality_engine.py` — OK
- `confidence_calibration_engine.py` — OK
- `outcome_analytics_engine.py` — OK
- `learning_health_engine.py` — OK
- `master_intelligence_score.py` — OK

## Self-Learning Engines

- `decision_replay_engine.py` — OK
- `pattern_discovery_engine.py` — OK
- `learning_recommendations_engine.py` — OK
- `confidence_optimizer_engine.py` — OK

## Market & Session Intelligence

- `market_open_readiness.py` — OK
- `market_session_snapshot.py` — OK
- `session_intelligence_engine.py` — OK
- `market_readiness_score.py` — OK

## Dashboard

- `dashboard_v2.py` — OK

## Key Data Files

- `decision_registry.csv` — OK
- `market_session_snapshots.csv` — OK
- `learning_weight_history.csv` — OK
- `adaptive_weights.csv` — OK

## Key Reports

- `daily_intelligence_report.txt` — OK
- `master_intelligence_score_summary.txt` — OK
- `learning_health_summary.txt` — OK
- `market_readiness_score_summary.txt` — OK
- `decision_replay_summary.txt` — OK
- `pattern_discovery_summary.txt` — OK
- `learning_recommendations_engine_summary.txt` — OK
- `confidence_optimizer_summary.txt` — OK

## Current Mode

```text
ANALYSIS_ONLY
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
```

## Operational Command

```bash
python3 daily_intelligence_runner.py
```

## Notes

- The system is structurally ready.
- The main limitation is insufficient completed WIN/LOSS outcomes.
- Do not enable broker execution until the platform has enough validated history.