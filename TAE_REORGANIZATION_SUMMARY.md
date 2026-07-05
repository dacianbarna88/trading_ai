# TAE Reorganization Summary

**Date:** 2026-07-05  
**Branch:** `cursor/x12b-legacy-archive-hotfix`  
**Base commit:** `50ebc0b` — TAE X.Decision checkpoint  
**Mode:** CONTROLLED_BUILD · NO_BROKER · NO_LIVE_EXECUTION_CHANGE · NO_COMMIT  
**Deliverable:** `tae_reorganization_registry.csv` (1222 rows)

---

## Executive verdict

**PASS — reorganization registry created and validated.**

The project is classified into a deterministic CSV registry suitable for controlled implementation, sprint scoping, and CSV-based tracking. No live execution files were modified. No files were deleted or renamed. Canonical spine (live bot → advisory gate → shadow ledger → X.10 attribution → shadow decision stack) is explicitly tagged **P0/P1 CANONICAL** or **SHADOW_ONLY**.

**Immediate gap:** 352 rows remain `UNKNOWN` / `NEEDS_REVIEW` (mostly root-level V14-era modules outside `research_core/`). These are **P3 review queue** items — not blockers for X.10 checkpoint commit.

---

## Git status summary

**Branch:** `cursor/x12b-legacy-archive-hotfix`

**Modified (uncommitted):** 18 paths — canonical doc sync, shadow `.md` regenerations, `tae_shadow_validation_report.py`, `market_open_runner.sh`

**Untracked (X.10 + audits):** `shadow_outcome_attribution*.py`, `tae_shadow_outcome_capture.py`, X.10 reports, master context docs

**New (this sprint):** `tae_reorganization_registry.csv`, `TAE_REORGANIZATION_SUMMARY.md`

**No commit performed.**

---

## CSV validation result

| Check | Result |
|-------|--------|
| CSV exists | **PASS** |
| Required columns present | **PASS** (9 columns) |
| Empty `file_path` values | **PASS** (0) |
| Enum fields use allowed values | **PASS** |
| Row count > 0 | **PASS** — **1222 rows** |

**Overall validation:** **PASS**

---

## Registry distribution

| Dimension | Top values |
|-----------|------------|
| **category** | RESEARCH (498), UNKNOWN (352), LEGACY (128), UNIFIED_RUNTIME (49), VALIDATION (48), GOVERNANCE (14) |
| **status** | ACTIVE (388), REPORT_ONLY (317), NEEDS_REVIEW (349), LEGACY (128), CANONICAL (24), SHADOW_ONLY (13) |
| **priority** | P3 (727), P2 (450), P0 (26), P1 (19) |
| **recommended_action** | KEEP_ACTIVE (390), REVIEW_BEFORE_USE (352), NO_ACTION (314), ARCHIVE_LATER (128), KEEP_CANONICAL (24), KEEP_SHADOW (14) |

---

## Canonical live files (P0)

| file_path | category | live_impact |
|-----------|----------|-------------|
| `live_bot.py` | LIVE_RUNTIME | YES |
| `portfolio.csv` | LIVE_RUNTIME | YES |
| `live_signals.csv` | LIVE_RUNTIME | YES |
| `watchlist.txt` | LIVE_RUNTIME | YES |
| `config/settings.py` | LIVE_RUNTIME | YES |
| `core/trades.py` | LIVE_RUNTIME | YES |
| `core/portfolio.py` | LIVE_RUNTIME | YES |
| `bot_controller.py` | LIVE_RUNTIME | PARTIAL |
| `market_session_guard.py` | INFRASTRUCTURE | PARTIAL |

**Rule:** Do not modify without explicit sprint approval.

---

## Advisory / governance / X.10 chain (P0)

| file_path | category | status |
|-----------|----------|--------|
| `research_core/governance/live_advisory_runtime.py` | ADVISORY_RUNTIME | CANONICAL |
| `research_core/governance/live_advisory_bridge.py` | ADVISORY_RUNTIME | CANONICAL |
| `research_core/governance/advisory_index.py` | ADVISORY_RUNTIME | CANONICAL |
| `tae_live_advisory.json` | ADVISORY_RUNTIME | CANONICAL |
| `research_core/governance/shadow_validation_ledger.py` | GOVERNANCE | CANONICAL |
| `tae_shadow_validation_events.csv` | GOVERNANCE | CANONICAL |
| `research_core/governance/shadow_outcome_attribution.py` | GOVERNANCE | SHADOW_ONLY |
| `tae_shadow_outcome_capture.py` | GOVERNANCE | SHADOW_ONLY |
| `tae_shadow_validation_report.py` | GOVERNANCE | ACTIVE |

---

## Decision / knowledge / unified (shadow + views)

| file_path | category | status |
|-----------|----------|--------|
| `tae_market_open_intelligence_runner.py` | DECISION | SHADOW_ONLY |
| `tae_decision_governor.py` | DECISION | SHADOW_ONLY |
| `tae_decision_replay_composer.py` | DECISION | SHADOW_ONLY |
| `tae_profit_protection_shadow.py` | DECISION | SHADOW_ONLY |
| `tae_profit_protection_validation.py` | DECISION | SHADOW_ONLY |
| `tae_stop_reentry_cooldown_audit.py` | DECISION | SHADOW_ONLY |
| `tae_knowledge_base.py` | KNOWLEDGE | SHADOW_ONLY |
| `tae_confidence_evolution.py` | KNOWLEDGE | SHADOW_ONLY |
| `tae_unified_runtime.json` | UNIFIED_RUNTIME | CANONICAL |
| `research_core/meta_intelligence_runtime/unified_runtime_ssot.py` | UNIFIED_RUNTIME | CANONICAL |

---

## Shadow-only files (summary)

**13 rows** tagged `SHADOW_ONLY` in registry — market-open stack, governor VIEW, knowledge VIEW, X.10 attribution, protect/cooldown/fade modules. All marked `KEEP_SHADOW` or `KEEP_CANONICAL` (ledger only). **None control live execution.**

---

## Reports-only files (summary)

**317 rows** tagged `REPORT_ONLY` — sprint summaries (`TAE_X*.md`), generated `tae_*.json` / `tae_*.md` artifacts, phase demo scripts. Action: `NO_ACTION` or `KEEP_ACTIVE` for regenerators. Safe to read; do not treat as execution SSOT.

Key governance reports (P0/P1):

- `PROJECT_BOOK.md`, `SESSION_START.md`, `TAE_DEVELOPMENT_PROTOCOL.md`
- `TAE_X10_EVIDENCE_MODEL.md`, `TAE_X10_IMPLEMENTATION_REPORT.md`, `TAE_X10_CHECKPOINT_VALIDATION_REPORT.md`

---

## Legacy and duplicate candidates

### Legacy (128 rows)

| Pattern | action |
|---------|--------|
| `archive/**` | ARCHIVE_LATER — X.12B post-SSOT archive |
| `restore_2026_06_22/**` | ARCHIVE_LATER — point-in-time restore |
| `daily_intelligence_runner.py` | ARCHIVE_LATER — not canonical |
| `outcome_assignment_engine.py` | ARCHIVE_LATER — V28; wrong SSOT for X.9/X.10 |

### Duplicate candidates (3 rows)

| file_path | notes |
|-----------|-------|
| `outcome_evaluator.py` | Overlaps X.10 shadow outcome path |
| `real_outcome_tracker.py` | Legacy real outcome tracker |
| `outcome_analytics_engine.py` | Legacy analytics |

**Rule:** Do not build parallel outcome pipelines — extend `shadow_outcome_attribution.py`.

---

## Canonical docs & validation entry points

| file_path | priority |
|-----------|----------|
| `PROJECT_BOOK.md` | P0 |
| `SESSION_START.md` | P0 |
| `TAE_DEVELOPMENT_PROTOCOL.md` | P0 |
| `tae_quick_health_check.py` | P0 |
| `tae_checkpoint.sh` | P1 |

---

## Immediate next implementation step

1. **Focused X.10 checkpoint commit** (when approved) — stage only:
   - `research_core/governance/shadow_outcome_attribution.py`
   - `research_core/governance/shadow_outcome_attribution_test.py`
   - `tae_shadow_outcome_capture.py`
   - `tae_shadow_validation_report.py`
   - X.10 reports + `tae_reorganization_registry.csv` + this summary
   - Exclude: canonical doc churn, regenerated shadow `.md`, `market_open_runner.sh`

2. **Refresh stale JSON** after live bot cycles:
   ```bash
   python3 tae_shadow_outcome_capture.py
   python3 tae_shadow_validation_report.py
   ```

3. **P3 review queue** — filter CSV where `status=NEEDS_REVIEW` for next reorganization pass (no broad audit required).

---

## Files created / modified (this task)

| Action | Path |
|--------|------|
| **Created** | `tae_reorganization_registry.csv` |
| **Created** | `TAE_REORGANIZATION_SUMMARY.md` |
| **Modified** | *(none)* |

---

## Final report

| Item | Value |
|------|-------|
| CSV row count | **1222** |
| Validation | **PASS** |
| Live execution changed | **NO** |
| Commit performed | **NO** |

*End of TAE_REORGANIZATION_SUMMARY.md*
