# TAE X.DECISION-1 — Decision Governor Report

**Date:** 2026-07-05  
**Sprint:** X.DECISION-1  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  

---

## 1. Objective

Implement a **read-only materialized advisory VIEW** that orchestrates existing JSON outputs into a single decision governor artifact — without re-running analysis modules or touching live execution.

---

## 2. What was built

| File | Role |
|------|------|
| `tae_decision_governor.py` | Read-only composer |
| `tae_decision_governor.json` | Structured governor VIEW |
| `tae_decision_governor.md` | Human-readable summary |

---

## 3. Reused helpers (no duplicated business logic)

| Helper | Source |
|--------|--------|
| `load_json()` | `tae_decision_replay_composer.py` |
| `merge_advisory_readiness()` | `tae_decision_replay_composer.py` |
| `sanitize_recommendation()` / `FORBIDDEN_RECOMMENDATIONS` | `tae_knowledge_base.py` |
| `UnifiedRuntimeSSOT` | `research_core/meta_intelligence_runtime/unified_runtime_ssot.py` |

Analysis logic for PROTECT-2, COOLDOWN-1, replay, confidence evolution, and knowledge ingest was **not** reimplemented.

---

## 4. Inputs consumed (read-only)

| File | Required | Used for |
|------|----------|----------|
| `tae_unified_runtime.json` | Yes | Per-ticker records, unified score summary |
| `tae_decision_replay.json` | Yes | Shadow verdict, readiness, churn tickers, blockers |
| `tae_live_advisory.json` | Optional | Live advisory mirror (`block_new_buy`, action) |
| `tae_profit_protection_validation.json` | Optional | PROTECT gates / readiness |
| `tae_profit_protection_shadow.json` | Optional | Presence flag only |
| `tae_stop_reentry_cooldown_audit.json` | Optional | COOLDOWN gates / readiness |
| `tae_knowledge_base.json` | Optional | Score decay entries (confidence_evolution source) |
| `tae_confidence_evolution.json` | Optional | Score decay candidates, promotion readiness |
| `tae_committee_runtime.json` | Optional | Committee weighted decision summary |
| `weighted_committee_decision.txt` | Optional | Presence flag only |

---

## 5. Governor output schema

Includes (no execution fields):

- `generated_at`, `mode`, `paper_only`, `no_broker`, `no_execution`
- `sources_loaded` / `sources_missing_required`
- `readiness` (PROTECT + COOLDOWN via replay SSOT)
- `overall_advisory_posture`
- `live_advisory_mirror`
- `shadow_verdict`
- `unified_runtime_summary`, `committee_summary`
- `blocker_summary` with source attribution
- `advisory_notes`
- `source_attribution` per domain
- `ticker_postures[]`: `ALLOWED` | `BLOCKED` | `WATCH` | `INSUFFICIENT_DATA`
- `posture_counts`, `recommendations` (SHADOW_ONLY)

---

## 6. Live run results (2026-07-05)

| Metric | Value |
|--------|-------|
| Sources loaded | **10/10** |
| Unified runtime tickers | **63** |
| Overall advisory posture | **NOT_READY** |
| Shadow readiness | NOT_READY (PROTECT WATCH, COOLDOWN NOT_READY) |
| Live advisory | SELL_ADVISORY, block_new_buy=false |
| Primary shadow cause | MISSED_PROFIT_PROTECTION |
| Blockers | **7** |
| Postures | ALLOWED 44 · WATCH 19 · BLOCKED 0 · INSUFFICIENT_DATA 0 |

WATCH tickers include score-decay shadows (MU, AMAT) and STRONG BUY names under NOT_READY shadow gates.

---

## 7. Per-ticker posture rules (summary)

| Condition | Posture |
|-----------|---------|
| Live `block_new_buy` + STRONG BUY | BLOCKED |
| Score decay candidate (confidence evolution / knowledge) | WATCH |
| STOP reentry churn in replay top costly | WATCH |
| Shadow gates NOT_READY + STRONG BUY | WATCH |
| TAKE PROFIT signal | WATCH |
| Default with unified record | ALLOWED |
| Missing score in record | INSUFFICIENT_DATA |

---

## 8. Validation

```text
python3 -m py_compile tae_decision_governor.py   # OK
python3 tae_decision_governor.py                 # OK
tae_decision_governor.json                       # exists
tae_decision_governor.md                         # exists
live_bot.py                                      # unchanged
No commit                                        # confirmed
```

---

## 9. Confirmations

| Constraint | Status |
|------------|--------|
| SHADOW_ONLY / PAPER_ONLY / NO_BROKER | ✅ |
| No live BUY/SELL / no execution fields | ✅ |
| No portfolio changes | ✅ |
| `live_bot.py` untouched | ✅ |
| Did not re-run protect/cooldown/replay/confidence/knowledge | ✅ |
| Materialized VIEW only | ✅ |

---

## 10. Recommended next step

**X.DECISION-2 — Live advisory bridge hook (optional):**

- Add read-only ingest of `tae_decision_governor.json` into `live_advisory_bridge.py` for richer blockers
- Still advisory-only — extend `block_new_buy` context, do not auto-trade
- Wire governor run after `tae_market_open_intelligence_runner.py` in `market_open_runner.sh`

Alternative: dashboard panel in `dashboard_tae_command_center.py` for governor posture table.

---

*Governor VIEW only. Live execution remains `live_bot.py`.*
