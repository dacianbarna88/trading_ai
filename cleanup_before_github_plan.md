# Cleanup Before GitHub — Safe Quarantine Plan

**Status:** PLAN ONLY — **no files have been moved.**  
**Created:** 2026-06-24  
**Goal:** Prepare `trading_ai` for first GitHub commit without deleting anything or changing live bot behavior.

---

## Safety rules (non-negotiable)

| Rule | Detail |
|------|--------|
| No deletions | Move only into quarantine; never `rm`. |
| No live bot edits | Do not modify `live_bot.py`, `live_bot_v5_1.py`, or `bot_controller.py` logic. |
| No portfolio edit | Do not modify `portfolio.csv`. |
| No dashboard edit | Do not modify `dashboard_v2.py`. |
| Protected directories | Do not move anything inside `config/`, `core/`, `data/`, `markets/`, `research/`, `utils/`, `intelligence/`. |
| Quarantine target | `archive/cleanup_before_github/` (preserve relative paths under that folder). |
| Approval gate | Execute moves only after you approve this plan. |

---

## Active system snapshot (what stays operational)

| Component | File(s) | Role |
|-----------|---------|------|
| Live bot (started by dashboard) | `live_bot.py` | `bot_controller.py` launches this as the primary process. |
| Portfolio engine | `live_bot_v5_1.py` | Used by `live_signal_refresh.py` (`manage_portfolio`). |
| Dashboard | `dashboard_v2.py` | Streamlit UI — unchanged. |
| Bot control | `bot_controller.py` | Start/stop + PID/status files. |
| Daily intelligence | `daily_intelligence_runner.py` | Runs V32 learning engines. |
| Signal refresh | `live_signal_refresh.py` | Regenerates signals + virtual portfolio updates. |
| Market session guard | `market_session_guard.py`, `market_session_guard.sh` | Session safety layer. |
| Position audit | `audit_open_positions.py` | Open-position integrity checks. |
| Fallback bot | `telegram_bot.py` | Fallback if `live_bot.py` missing (keep). |

**Note:** Old `live_bot` variants (`live_bot_v4_step4.py`, `live_bot_optimized.py`, etc.) already live under `archive/` — they are **not** moved again; existing `archive/` tree stays as-is.

---

## Manifest summary

Full line-by-line decisions: `cleanup_before_github_manifest.csv`

| Action | Count | Meaning |
|--------|-------|---------|
| **KEEP** | 114 | Stay in place (active code, dashboard inputs, protected dirs). |
| **MOVE_TO_CLEANUP_ARCHIVE** | 154 | Safe quarantine candidates after approval. |
| **REVIEW_MANUAL** | 157 | Human decision before any move. |

**Root-level quarantine candidates:** 153 files (mostly generated summaries, `*_before_*` snapshots, legacy entrypoints, version audit scripts).

---

## `dashboard_v2.py` — files that MUST stay (verified)

These `*_summary.txt` files are read by the dashboard. **Do not quarantine them** even though they are generated artifacts:

```
adaptive_allocation_summary.txt
adaptive_decision_guard_summary.txt
adaptive_strategic_risk_summary.txt
allocation_gap_summary.txt
benchmark_data_layer_summary.txt
benchmark_execution_protected_summary.txt
committee_learning_summary.txt
confidence_calibration_summary.txt
confidence_evolution_summary.txt
confidence_optimizer_summary.txt
decision_quality_summary.txt
decision_replay_summary.txt
feedback_update_summary.txt
historical_pattern_summary.txt
learning_automation_summary.txt
learning_health_summary.txt
learning_recommendations_engine_summary.txt
market_forecast_summary.txt
market_readiness_score_summary.txt
master_intelligence_score_summary.txt
outcome_evaluator_summary.txt
outcome_validation_summary.txt
paper_trading_decision_summary.txt
pattern_discovery_summary.txt
portfolio_action_summary.txt
position_intelligence_summary.txt
return_tracking_summary.txt
session_intelligence_summary.txt
strategic_committee_summary.txt
strategic_conflict_summary.txt
strategic_decision_summary.txt
strategic_rebalance_summary.txt
strategic_risk_summary.txt
weighted_committee_decision_summary.txt
weighted_committee_summary.txt
```

Other dashboard inputs (not `*_summary.txt` but required): `portfolio.csv`, `live_signals.csv`, `signals.csv`, `alerts_log.csv`, `bot_status.txt`, `bot_output.log`, `decision_accuracy_report.txt`, `committee_learning_analytics.txt`, `decision_history.log`, `daily_intelligence_report.txt`, plus the CSV/JSON files listed in the manifest as **KEEP**.

**Example — safe to quarantine:** `threshold_virtual_tracker_summary.txt`, `learning_engine_summary.txt`, `hard_risk_guardian_summary.txt` (active per `PROJECT_STATUS.md`, but not displayed in `dashboard_v2.py`).

---

## Quarantine categories (what moves after approval)

### 1. Pattern matches (automatic candidates)

| Pattern | Examples | Count (root) |
|---------|----------|--------------|
| `*_before_*` | `portfolio_before_v37_4_*.csv`, `bot_output_before_extra_cash_test.log`, `committee_learning_engine_before_v9_6.py` | ~12 |
| `*_old*` | `bot_error_old.log` | 1 |
| `*_backup*` | `watchlist_backup.txt`, `crontab_backup_*.txt`, `cloud_backup_sync.py` | ~6 |
| `*_copy*` | (none at root currently) | 0 |

Portfolio backups (`portfolio_before_*.csv`) are **not** `portfolio.csv` — safe to quarantine.

### 2. Legacy entrypoints / autopilots

Move to quarantine (superseded by `live_bot.py` + `bot_controller.py`):

- `bot.py`, `main.py`, `run_dashboard.py`
- `autopilot.py`, `full_autopilot.py`, `market_autopilot_final.py`
- `backtest.py`, `advanced_backtest.py`

### 3. Version audit / test scripts (not active bot)

Move to quarantine:

- `v37_4_buy_sell_logic_test.py` … `v42_engine.py`
- `v41_*` experimental scripts (`v41_live_observer.py`, `v41_fusion_engine.py`, etc.)
- `outcome_evaluator_test.py`, `decision_registry_test.csv`

### 4. Generated summaries not read by dashboard

~70 root `*_summary.txt` files (e.g. threshold stack, sector/macro summaries, historical addon summaries). Regenerated by engines; dashboard shows warnings if missing but does not reference these paths.

### 5. Generated reports / checkpoints

- `*_report.txt`, `*_report.csv` (except `position_intelligence_report.csv` — **KEEP**)
- `V28_0_CHECKPOINT_STATUS.txt` … `V32_0_PROJECT_STATUS.txt`
- `Trading AI Dashboard.pdf`
- Prior cleanup audit outputs (`project_cleanup_audit*`)

### 6. Subdirectory pattern matches (non-protected only)

Shallow scan found additional `*_before_*` files outside protected dirs, e.g.:

- `confidence_intelligence/weighted_committee_engine_before_v28_1.py`

`core/*_before_*` files remain **KEEP** (protected directory).

---

## REVIEW_MANUAL — decide before moving

These are **not** auto-quarantined because they may still be cron/runner dependencies or active engines from `PROJECT_STATUS.md`:

### Likely KEEP (recommend after quick cron check)

| File | Why |
|------|-----|
| `threshold_virtual_tracker.py` | Active system (V14.5). |
| `threshold_test_simulator.py`, `threshold_outcome_auditor.py` | Threshold pipeline. |
| `learning_engine.py`, `learning_insights.py`, `learning_scoreboard.py` | Learning stack. |
| `position_intelligence.py` | Position intelligence engine. |
| `hard_risk_guardian.py`, `overnight_gap_risk_guard.py` | Risk guards. |
| `missed_winners_audit.py`, `post_sell_audit.py`, `rebalance_edge_engine.py` | Audit engines. |
| `market_open_runner.sh`, `market_close_runner.sh`, `awake_guard.sh` | Scheduler wrappers. |
| `telegram_bot.py` | Fallback bot entry (manifest: KEEP). |

### Likely quarantine OR gitignore only

| Item | Recommendation |
|------|----------------|
| `*.log`, `*.pid` | **Do not move** — rely on `.gitignore` (`bot_output.log` stays local). |
| `backups/`, `restore_2026_06_22/`, `backup_v41_pre_market/` | Gitignore only; already listed in `.gitignore`. |
| `data_cache/` | Gitignore only (cached market data). |
| `strategic_intelligence/`, `sector_intelligence/`, `macro_intelligence/`, `confidence_intelligence/`, `benchmark_intelligence/` | Track source in git OR consolidate later — not part of this quarantine pass. |

### Root Python modules (~90 files)

Many one-off engines at repo root (`adaptive_strategic_risk.py`, `strategic_committee.py`, `committee_learning_engine.py`, etc.) feed the dashboard indirectly by **writing** the KEEP summary files. **Recommendation:** KEEP engine `.py` files for first commit; quarantine only their non-dashboard summary outputs.

---

## Directories — do not relocate

| Directory | Action |
|-----------|--------|
| `archive/` (existing snapshots) | **KEEP structure** — do not bulk-move into `cleanup_before_github/`. |
| `config/`, `core/`, `data/`, `markets/`, `research/`, `utils/`, `intelligence/` | **KEEP** — no moves. |
| `venv/`, `__pycache__/` | Gitignore only. |
| `backups/`, `restore_2026_06_22/` | Gitignore only (already in `.gitignore`). |

---

## Recommended `.gitignore` tweaks (separate from quarantine)

Current `.gitignore` ignores all `*.csv`, `*.txt`, `*.json` globally — which also hides source you may want on GitHub (e.g. `watchlist_us.txt`, `validation_rules.json`).

**Suggested follow-up (after cleanup approval):**

1. Stop ignoring all `*.py` and `*.md` (already tracked).
2. Replace blanket `*.txt` / `*.csv` / `*.json` ignores with explicit runtime paths:
   - `portfolio.csv`, `live_signals.csv`, `bot_*.log`, `*.pid`
   - `*_summary.txt` (optional — or allow dashboard summaries)
3. Keep ignoring `archive/`, `backups/`, `venv/`, `__pycache__/`.

This is a **commit strategy** decision, not a file move.

---

## Execution procedure (after you approve)

```bash
cd ~/Desktop/trading_ai

# 1. Create quarantine folder
mkdir -p archive/cleanup_before_github

# 2. Dry-run: list root MOVE targets from manifest
awk -F, '$2=="MOVE_TO_CLEANUP_ARCHIVE" && $1 !~ /\/"/ {print $1}' cleanup_before_github_manifest.csv

# 3. Move one category at a time (example: before-snapshots)
# for f in portfolio_before_*.csv bot_output_before_*.log; do
#   [ -f "$f" ] && mkdir -p "archive/cleanup_before_github/$(dirname "$f")" && mv "$f" "archive/cleanup_before_github/$f"
# done

# 4. Verify bot + dashboard still start
python3 -c "import live_bot, live_bot_v5_1, dashboard_v2, bot_controller"
streamlit run dashboard_v2.py   # manual smoke test

# 5. git status — confirm only quarantine moves, no protected edits
```

**Move command pattern:** preserve relative path under quarantine:

```bash
rel="threshold_virtual_tracker_summary.txt"
mkdir -p "archive/cleanup_before_github/$(dirname "$rel")"
mv "$rel" "archive/cleanup_before_github/$rel"
```

---

## Approval checklist

- [ ] Reviewed `cleanup_before_github_manifest.csv`
- [ ] Confirmed all dashboard `*_summary.txt` files remain **KEEP**
- [ ] Confirmed `portfolio.csv` untouched
- [ ] Resolved **REVIEW_MANUAL** items for active engines (threshold, learning, position intelligence)
- [ ] Approved quarantine of legacy entrypoints and `*_before_*` snapshots
- [ ] Ready to run moves into `archive/cleanup_before_github/`

---

## Files produced by this plan

| File | Purpose |
|------|---------|
| `cleanup_before_github_plan.md` | This document |
| `cleanup_before_github_manifest.csv` | Per-path Action + Reason |

**No other project files were modified.**
