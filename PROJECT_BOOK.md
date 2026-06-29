# Trading AI — PROJECT BOOK (Canonical Journal)

**Last updated:** 2026-06-29  
**Latest sprint:** X.9 — Connected Shadow Validation Runtime Ledger  
**Governance mode:** ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION  
**Canonical runtime:** `live_bot.py` (not `live_bot_v5_1.py`)

> **Read first each session:** `SESSION_START.md`  
> **End each sprint:** `bash tae_checkpoint.sh` then update this file + commit

---

## 1. Current Runtime Status

| Component | Status | Entry point |
|-----------|--------|-------------|
| Live bot | **CANONICAL** | `live_bot.py` via `bot_controller.start_bot()` |
| Dashboard | Active | `dashboard_v2.py` (Streamlit port 8501) |
| Autostart | Active | `startup_runner.sh` → `market_session_guard.py` |
| Session gate | Per-ticker | `markets/market_hours.py` |
| Quick health | TAE official | `python3 tae_quick_health_check.py` |
| TAE stable label | V9.6 | See `TAE_IX_6_V96_STABLE_RELEASE_REPORT.md` |

**Live bot decision spine:** `watchlist.txt` → yfinance → score (RSI/SMA50) → `live_signals.csv` → `manage_portfolio()` → `portfolio.csv`

**X.9 observability:** each BUY evaluation in `manage_portfolio()` logs to `tae_shadow_validation_events.csv` via `shadow_validation_ledger.py` (BUY path only; SELL unchanged).

**Protected files (do not change without explicit sprint):** `live_bot.py` (trading logic), `portfolio.csv`, `config/settings.py`, `core/trades.py`

---

## 2. Current TAE Architecture

```
LIVE (canonical)
  live_bot.py ──writes──► live_signals.csv, portfolio.csv
       │
       │ reads (X.8 risk gate only)
       ▼
  tae_live_advisory.json ◄── live_advisory_bridge.py ◄── tae_advisory_index.json + tae_*.json + CSV read-only
       │
       │ BUY path observability (X.9)
       ▼
  tae_shadow_validation_events.csv ◄── shadow_validation_ledger.py (append-only, failure-safe)
       │
       ▼
  tae_shadow_validation_summary.json ◄── tae_shadow_validation_report.py (report-only)

TAE RESEARCH (report / paper)
  tae_full_ecosystem_run.py → orchestrator → evidence → daily runner → ranking → registry → gates → governance
  Phase X: discovery → simulation → historical research/execution/analysis → meta intelligence → event memory scaffold

OBSERVABILITY (UI)
  dashboard_v2.py → TAE Intelligence Reports tab + Advisory Index + live CSV display

GOVERNANCE (X.7B–X.9)
  advisory_index.py → tae_advisory_index.json
  live_advisory_bridge.py → tae_live_advisory.json
  live_advisory_runtime.py → live_bot BUY risk filter
  shadow_validation_ledger.py → BUY evaluation event ledger (CONNECTED_SHADOW_VALIDATION)
```

**Flow after X.9:**

`LIVE → portfolio/live_signals → TAE reports → advisory index → live advisory → live_bot risk gate (BUY only) → shadow validation ledger (BUY observability)`

---

## 3. What Exists

### Runtime & ops
- `live_bot.py`, `bot_controller.py`, `market_session_guard.py`, `dashboard_v2.py`
- `startup_runner.sh`, `awake_guard.sh`, `tools/morning_control_room.sh`

### TAE core (`research_core/`)
- **Governance:** daily intelligence, advisory index, live advisory bridge/runtime, **shadow validation ledger (X.9)**
- **Orchestrator:** ecosystem orchestrator, full ecosystem run
- **Evidence:** evidence engine, integration gate, gap registration
- **Strategy evolution:** daily runner, candidate registry, parallel paper validator, continuous ranking, promotion gate, paper tracking
- **Performance / accounting:** integrity audit, independent double entry, strategic performance audit
- **Phase X research:** strategy discovery/simulation, historical research/execution/results analysis
- **Meta:** meta intelligence, meta evolution, recommendation outcome
- **Market intelligence:** event schema + empty event memory (X.6A scaffold)
- **Integration adapters:** strategy, evidence, accounting, simulation, orchestrator, runtime

### Demos & entry points
- `tae_quick_health_check.py` — daily health
- `tae_full_ecosystem_run.py` — full pipeline
- `tae_advisory_index_demo.py`, `tae_live_advisory_demo.py` — governance artifacts
- `tae_shadow_validation_report.py` — aggregates shadow ledger → summary JSON (X.9)
- 77+ `tae_phase*_demo.py` scripts (see glob; most superseded by full ecosystem for daily ops)

### Reports
- **~87** `tae_*.json` files in project root (gitignored)
- Sprint summaries: `TAE_X7A` … `TAE_X9`, connectivity audits X.7

### X.9 — Connected Shadow Validation Ledger (COMPLETED)

| Item | Path / detail |
|------|----------------|
| Ledger module | `research_core/governance/shadow_validation_ledger.py` |
| Report script | `tae_shadow_validation_report.py` |
| Events artifact | `tae_shadow_validation_events.csv` (append-only; auto-created) |
| Summary artifact | `tae_shadow_validation_summary.json` (report-only) |
| Live integration | Direct in **BUY path** of `live_bot.py` adjacent to `should_block_new_buy()` |
| Event types | `BUY_ALLOWED`, `BUY_BLOCKED_BY_TAE`, `BUY_SKIPPED_OTHER_REASON` |
| SELL branch | **Not modified** |
| Outcome tracking | `outcome_tracking_status: PENDING_NEXT_PHASE` (no forward PnL yet) |
| Mode | `CONNECTED_SHADOW_VALIDATION` · `live_trading_impact: NONE` |
| Safety | Ledger failure → warning log only; never stops bot; cannot execute BUY/SELL |

---

## 4. What Is Connected To LIVE

| Link | Mechanism | Impact |
|------|-----------|--------|
| `live_bot.py` → `portfolio.csv`, `live_signals.csv` | Direct write | BUY / SELL (paper) |
| `live_bot.py` → `tae_live_advisory.json` | `live_advisory_runtime.py` | **RISK_ADVISORY blocks new BUY only** |
| `live_bot.py` → `tae_shadow_validation_events.csv` | `shadow_validation_ledger.py` (X.9) | **Observability only** — BUY evaluations logged |
| `tae_shadow_validation_report.py` → summary JSON | Read events CSV | Report-only aggregation |
| `dashboard_v2.py` → live CSV + bot start/stop | Read / process control | Display + start bot (no TAE data feed) |
| TAE modules → `portfolio.csv`, `live_signals.csv` | Read-only audit | **No write back to live** |

**X.8 integration rules (mandatory):**
- TAE **does not force BUY**
- TAE **does not force SELL**
- `RISK_ADVISORY` → block **new BUY only**; SELL / STOP / TAKE PROFIT **unchanged**
- `BUY_ADVISORY` → log only, no auto-buy
- `SELL_ADVISORY` → log only, no auto-sell
- Missing/stale advisory → SAFE fallback (no BUY block unless `stale_block_buy=true`)

**X.9 observability rules (mandatory):**
- Ledger logs **BUY evaluation only** — `BUY_ALLOWED`, `BUY_BLOCKED_BY_TAE`, `BUY_SKIPPED_OTHER_REASON`
- **SELL branch not modified**
- Ledger **cannot** execute trades, modify advisory, portfolio, or signals
- Ledger write failure → warning only; **bot continues**
- `tae_shadow_validation_events.csv` and summary JSON are **artifacts only**

---

## 5. What Is Report-Only

All `tae_*.json` / `tae_*.txt` research outputs except the advisory consumption path above.

Key report-only modules:
- Meta intelligence / meta evolution (recommendations for human review)
- Historical execution & results analysis
- Strategy discovery, simulation, ranking, registry
- Evidence engine & integration gate
- Full ecosystem run, quick health, daily intelligence
- Dashboard TAE tab (read-only display)

**No automatic path:** `tae_*.json` → `watchlist.txt` / scoring thresholds / `config/settings.py`

---

## 6. What Is Scaffold-Only

| Item | State |
|------|--------|
| `tae_event_memory.json` | 0 events; schema + validation only (X.6A) |
| `TAE_MARKET_INTELLIGENCE_BLUEPRINT.md` | Design doc; no ingestion/models |
| `tae_implementation_patch.json` | Human-apply proposals only |
| Event memory ingestion / live news | **Not built** |

---

## 7. What Is Legacy / Orphan

**Not canonical runtime — do not wire without explicit sprint:**

| Path | Notes |
|------|--------|
| `live_bot_v5_1.py` | Uses `research/signals.py`, `config/settings.py`; superseded by `live_bot.py` |
| `live_signal_refresh.py` | Orphan refresh chain |
| `telegram_bot.py` | Reads legacy `signals.csv`, not `live_signals.csv` |
| `research/market_scanner.py` | Can rewrite `watchlist.txt`; not called by canonical `live_bot.py` |
| `signal_to_decision_engine.py` → `decision_registry.csv` | Paper registry; not read by `live_bot.py` |
| `daily_intelligence_runner.py` | V32 learning stack; use `tae_quick_health_check.py` |
| V12–V14 threshold/learning scripts | Parallel legacy stack per `PROJECT_STATUS.md` |

---

## 8. Current Canonical Files

### Runtime
- `live_bot.py`, `bot_controller.py`, `dashboard_v2.py`
- `markets/market_hours.py`, `markets/market_config.py`

### TAE governance (Phase X.7–X.9)
- `research_core/governance/advisory_index.py`
- `research_core/governance/advisory_index_report.py`
- `research_core/governance/live_advisory_bridge.py`
- `research_core/governance/live_advisory_runtime.py`
- `research_core/governance/shadow_validation_ledger.py` (X.9)
- `tae_advisory_index_demo.py`, `tae_live_advisory_demo.py`
- `tae_shadow_validation_report.py` (X.9)

### TAE constitution
- `TAE_DEVELOPMENT_PROTOCOL.md`, `TAE_GIT_GOVERNANCE.md`, `TAE_ARCHITECTURE.md`

### Session / checkpoint
- `PROJECT_BOOK.md` (this file), `SESSION_START.md`, `tae_checkpoint.sh`

---

## 9. Current Generated Artifacts

| Artifact | Producer | Consumer |
|----------|----------|----------|
| `tae_advisory_index.json` | `tae_advisory_index_demo.py` | Dashboard, live advisory bridge |
| `tae_live_advisory.json` | `tae_live_advisory_demo.py` | `live_bot.py` (risk gate), dashboard potential |
| `tae_shadow_validation_events.csv` | `live_bot.py` via ledger (X.9) | Report script, ops review |
| `tae_shadow_validation_summary.json` | `tae_shadow_validation_report.py` (X.9) | Dashboard potential, ops |
| `tae_quick_health_check.json` | `tae_quick_health_check.py` | Health monitoring |
| `tae_full_ecosystem_run.json` | `tae_full_ecosystem_run.py` | Orchestration audit |
| 85+ other `tae_*.json` | Phase demos / ecosystem | Dashboard, meta, audits |

All `*.json` in root are **gitignored** — regenerate via demos; do not commit unless policy changes.

---

## 10. Current Trading Impact

| Source | BUY | SELL | Sizing | Thresholds |
|--------|-----|------|--------|------------|
| `live_bot.py` inline rules | Yes | Yes | Yes | Yes (hardcoded in file) |
| TAE advisory (X.8) | **Block new only on RISK** | No | No | No |
| TAE shadow ledger (X.9) | **Log only** | No | No | No |
| TAE reports | No | No | No | No |
| Dashboard | No | No | No | No |

**Classification:** TAE = **CONTROLLED_RUNTIME_INTEGRATION** (X.8 advisory risk gate) + **CONNECTED_OBSERVABILITY** (X.9 shadow ledger; no execution impact).

---

## 11. What Must NOT Be Rebuilt

Do **not** recreate under new names — reuse canonical modules:

| Already exists | Do not duplicate |
|----------------|------------------|
| `research_core/orchestrator/ecosystem_orchestrator.py` | New “master runner” scripts |
| `research_core/full_ecosystem/full_ecosystem_run.py` | Another daily chain |
| `research_core/runtime/quick_health_wrapper.py` | Ad-hoc health scripts |
| `research_core/strategy_evolution/daily_runner.py` | Parallel evolution runners |
| `research_core/evidence_engine/evidence_registry.py` | Second evidence SOT |
| `research_core/governance/advisory_index.py` | Manual JSON aggregation |
| `research_core/governance/live_advisory_bridge.py` | New live↔TAE bridge |
| `research_core/governance/live_advisory_runtime.py` | Inline JSON parsing in `live_bot.py` |
| `research_core/governance/shadow_validation_ledger.py` | Second BUY event logger / inline CSV writes in `live_bot.py` |
| `research_core/market_intelligence/event_schema.py` | New event ID scheme |
| Phase X historical pipeline | Re-run analysis under new filenames |
| Dashboard TAE tab (X.7A) | Separate JSON viewer |
| X.8 live bot gate | Second BUY blocker |
| X.9 shadow ledger | Rebuild BUY observability under new name |

**Before any new module:** grep `research_core/`, read `TAE_CONNECTIVITY_AUDIT_X7.md`, check `tae_ecosystem_inventory.json`.

---

## 12. Next Allowed Sprint

**Recommended:** **X.10 — Outcome Tracking / Attribution for Blocked BUYs**

**Prerequisite:** X.9 ledger must have accumulated real events in `tae_shadow_validation_events.csv` (run live bot through market cycles first).

Scope (allowed):
- Forward PnL / avoided-loss / missed-gain attribution on `BUY_BLOCKED_BY_TAE` events
- Compare blocked vs allowed BUY outcomes over holding window
- Reports only — **no change to SELL logic, sizing, scoring, or forced execution**
- Set `outcome_tracking_status` beyond `PENDING_NEXT_PHASE` when implemented

**Not allowed without architect approval:**
- TAE-driven sizing, score changes, threshold writes
- Auto-execution from meta evolution / ranking
- Rewriting `live_bot.py` scoring engine
- Rebuilding orchestrator, evidence SOT, advisory stack, or shadow ledger (X.9)

---

## 13. Session Start Checklist

1. Read `SESSION_START.md`
2. `cd` to project root
3. `bash tae_checkpoint.sh` (or quick: `git status` + `python3 tae_quick_health_check.py`)
4. Confirm canonical runtime: **`live_bot.py`** (not v5_1)
5. Regenerate if stale: `python3 tae_live_advisory_demo.py`
6. Check `bot_status.txt`, `tae_live_advisory.json` action field
7. Review this `PROJECT_BOOK.md` §3–§11 before proposing new modules

---

## 14. Sprint Completion Checklist

1. Run `bash tae_checkpoint.sh`
2. Update **this file** (`PROJECT_BOOK.md`): §1, §3, §10, §12
3. Update `PROJECT_STATUS.md` sprint section (optional short pointer)
4. Add `TAE_X<N>_*.md` sprint summary
5. Verify protected files unchanged unless sprint explicitly allowed
6. `git add` relevant files (not `tae_*.json` unless policy change)
7. `git commit -m "TAE Sprint X.N — …"`
8. `git push` when ready
9. Record commit hash below

### Sprint history (recent)

| Sprint | Summary doc | Notes |
|--------|-------------|-------|
| X.7 | `TAE_CONNECTIVITY_AUDIT_X7.md` | Direct live map |
| X.7 fix | `TAE_INDIRECT_INTEGRATION_AUDIT_X7_FIX.md` | Artifact chains |
| X.7A | `TAE_X7A_DASHBOARD_VISIBILITY_SUMMARY.md` | Dashboard TAE tab |
| X.7B | `TAE_X7B_ADVISORY_INDEX_SUMMARY.md` | `tae_advisory_index.json` |
| X.7C | `TAE_X7C_LIVE_ADVISORY_BRIDGE_SUMMARY.md` | `tae_live_advisory.json` |
| X.8 | `TAE_X8_LIVE_BOT_ADVISORY_INTEGRATION_SUMMARY.md` | Live BUY risk gate |
| X.9 | `TAE_X9_SHADOW_VALIDATION_SUMMARY.md` | Connected shadow validation ledger |
| **Governance reset** | `TAE_GOVERNANCE_RESET_SUMMARY.md` | PROJECT_BOOK + checkpoint |

---

## Reference index (TAE_*.md)

| Document | Purpose |
|----------|---------|
| `TAE_DEVELOPMENT_PROTOCOL.md` | Constitution |
| `TAE_GIT_GOVERNANCE.md` | Git rules |
| `TAE_ARCHITECTURE.md` | High-level architecture |
| `TAE_MARKET_INTELLIGENCE_BLUEPRINT.md` | Future market intel (not implemented) |
| `TAE_CONNECTIVITY_AUDIT_X7.md` | Direct connectivity audit |
| `TAE_INDIRECT_INTEGRATION_AUDIT_X7_FIX.md` | Indirect artifact audit |
| `TAE_X7A` … `TAE_X9` | Sprint summaries |
| `TAE_PROJECT_STATUS.md` | TAE-specific status snapshot |
| `PROJECT_STATUS.md` | Combined project + TAE checkpoint notes |
| `PROJECT_MAP.md` | Legacy V32 map (partially stale) |

---

*End of PROJECT_BOOK.md*
