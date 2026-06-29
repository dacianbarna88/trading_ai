# TAE Sprint X.7C — Live Advisory Signal Bridge Summary

**Date:** 2026-06-29  
**Mode:** PAPER_ONLY | ADVISORY_ONLY | NO_AUTO_EXECUTION  
**Live trading impact:** NONE

---

## Objective

Read-only bridge combining `tae_advisory_index.json`, live CSV snapshots, and selected TAE reports into a single advisory artifact for human review — **no execution path**.

---

## Deliverables

| Artifact | Role |
|----------|------|
| `research_core/governance/live_advisory_bridge.py` | Bridge builder + advisory logic |
| `tae_live_advisory_demo.py` | Regenerate `tae_live_advisory.json` |
| `tae_live_advisory.json` | Canonical live advisory output |
| `TAE_X7C_LIVE_ADVISORY_BRIDGE_SUMMARY.md` | This document |

---

## Inputs (read-only)

| Source | Usage |
|--------|--------|
| `tae_advisory_index.json` | Report counts, warnings, dominant verdict |
| `portfolio.csv` | Open positions, cash estimate, losing positions |
| `live_signals.csv` | Signal counts (if present) |
| `bot_status.txt` | Runtime bot state |
| `tae_quick_health_check.json` | Health gate |
| `tae_meta_intelligence.json` | Ecosystem confidence |
| `tae_continuous_strategy_ranking.json` | Ranking context |
| `tae_historical_results_analysis.json` | **Median-first** robust shortlist metrics |
| `tae_strategic_performance_audit.json` | Performance risk flags |
| `tae_full_ecosystem_run.json` | Ecosystem run context |
| `tae_ecosystem_orchestrator.json` | Orchestrator context |

**Not modified:** `live_bot.py`, `portfolio.csv`, `live_signals.csv`, BUY/SELL logic.

---

## Output schema (`tae.live_advisory.v1`)

Required fields present:

1. `mode`: `"PAPER_ONLY_ADVISORY"`
2. `live_trading_impact`: `"NONE"`
3. `generated_at`
4. `runtime_snapshot` — open positions, signal counts, cash, bot status
5. `tae_snapshot` — total/valid reports, warning_count, dominant_status
6. `advisory` — action, confidence (0–100), reasons[], blockers[]
7. `safety` — no_broker, no_execution, live_bot_not_modified, advisory_only

---

## Advisory rules (conservative)

| Action | Conditions |
|--------|------------|
| **RISK_ADVISORY** | Invalid JSON in index; warning_count ≥ 3; quick health not ready; performance audit anomaly; ≥2 losing open positions; mean/median historical contradiction |
| **SELL_ADVISORY** | TAKE PROFIT live signals or ≥1 open position ≤ −3% PnL (if not already RISK) |
| **BUY_ADVISORY** | Strict alignment only: valid index, zero invalid JSON, zero warnings, HIGH meta confidence, quick health ready, live STRONG BUY (score ≥ 80), open slots available, **median robust Sharpe ≥ 0.5** — **not** from positive reports alone |
| **NO_ACTION** | Default when blockers exist or criteria not met |

Warnings reduce confidence (−4 per warning, cap −25).

---

## Sample run (2026-06-29)

```
Action:       RISK_ADVISORY
Confidence:   53
Open positions: 5
Live signals:  15 (5 STRONG BUY, 4 TAKE PROFIT)
TAE reports:   85/85 valid
Warnings:      7 aggregated
Bot status:    STOPPED
Blocker:       Elevated aggregated warning count (7)
```

BUY_ADVISORY **not** emitted despite 5 STRONG BUY signals — warnings + conservative gates.

---

## Validation

| Check | Result |
|-------|--------|
| `python3 tae_live_advisory_demo.py` | PASS |
| `python3 -m json.tool tae_live_advisory.json` | PASS |
| `python3 -m py_compile live_advisory_bridge.py` | PASS |
| `python3 -m py_compile tae_live_advisory_demo.py` | PASS |
| `live_bot.py` modified | **NO** |

Regenerate:

```bash
python3 tae_live_advisory_demo.py
```

Note: `tae_live_advisory.json` is gitignored (`*.json`) like other TAE artifacts.

---

## Git status

```
?? research_core/governance/live_advisory_bridge.py
?? tae_live_advisory_demo.py
?? TAE_X7C_LIVE_ADVISORY_BRIDGE_SUMMARY.md
(live_bot.py unchanged)
```

---

*End of X.7C summary.*
