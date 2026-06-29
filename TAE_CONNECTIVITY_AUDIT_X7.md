# TAE Connectivity Audit — Sprint X.7

**Date:** 2026-06-29  
**Mode:** AUDIT ONLY — no code changes, no new modules  
**Objective:** Harta reală de conectivitate — ce influențează deciziile LIVE vs ce este research/report/scaffold

---

## 1. Executive Summary

### 1.1 LIVE decision spine (singura cale de execuție BUY/SELL)

```
watchlist.txt
     │
     ▼
live_bot.py  ──► yfinance (prețuri) ──► live_signals.csv
     │                    │
     │                    └── markets/market_hours.py (session gate per ticker)
     │
     ├── portfolio.csv  ◄── BUY / SELL writes (PAPER_ONLY)
     ├── alerts_log.csv
     ├── bot_status.txt
     └── subprocess → position_intelligence.py (post-cycle refresh)

bot_controller.py ──starts──► live_bot.py
market_session_guard.py ──starts──► live_bot.py + dashboard (process only)
dashboard_v2.py ──reads──► portfolio.csv, live_signals.csv (display + start/stop bot)
```

**Concluzie critică:** `live_bot.py` **nu importă** `research_core/*`, **nu citește** niciun `tae_*.json`, și **nu consumă** ranking/registry/meta/evidence/historical/event memory. Deciziile BUY/SELL sunt 100% locale (scor RSI/SMA50, praguri hardcoded, SPY regime, session per ticker).

### 1.2 Research / report spine (nu atinge live_bot)

```
tae_full_ecosystem_run.py
  → quick health → orchestrator → evidence engine → daily runner
    → registry → parallel validation → continuous ranking
    → promotion gate → paper tracking → performance → governance
  → tae_* JSON reports

tae_phase10_* demos (discovery, simulation, historical research/execution/analysis)
  → tae_strategy_discovery.json → tae_strategy_simulation.json
  → tae_historical_research.json → tae_historical_execution.json
  → tae_historical_results_analysis.json

tae_phase10_meta_intelligence_demo / meta_evolution_demo
  → tae_meta_intelligence.json → tae_meta_evolution.json

tae_phase11_event_memory_demo
  → tae_event_memory.json (0 events, scaffold)
```

**Concluzie:** Întreg ecosistemul TAE Phase VIII–X produce rapoarte JSON/TXT și citește `portfolio.csv` **read-only** pentru audit/paper validation — **fără feedback loop în live_bot**.

### 1.3 Classification legend

| Label | Meaning |
|-------|---------|
| **CONNECTED_TO_LIVE** | În lanțul de execuție live sau scrie/citește artefacte pe care live_bot le folosește |
| **REPORT_ONLY** | Produce/consumă rapoarte; nu modifică decizii live |
| **SCAFFOLD_ONLY** | Schema/demo fără date sau fără consumatori downstream |
| **ORPHAN** | Produs dar fără consumator în lanț (excl. demo/manual) |

---

## 2. LIVE vs RESEARCH Boundary Matrix

| Zone | Influențează BUY | Influențează SELL | Scrie portfolio.csv | Citește portfolio.csv |
|------|------------------|-------------------|---------------------|------------------------|
| live_bot.py | **DA** | **DA** | **DA** | **DA** |
| dashboard_v2.py | Indirect (start bot) | Indirect | NU | DA (display) |
| market_session_guard | NU (doar pornește proces) | NU | NU | NU |
| research_core/* | NU | NU | NU | Read-only (unele module) |
| tae_* pipeline | NU | NU | NU | Read-only (audit/registry) |

---

## 3. Module-by-Module Audit

### 3.1 live_bot.py

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `live_bot.py` (monolith ~640 lines; no research_core) |
| 2 | **Produces** | `live_signals.csv`, `portfolio.csv`, `alerts_log.csv`, `bot_status.txt`, `bot_output.log` |
| 3 | **Consumes** | `watchlist.txt`, `portfolio.csv`, `yfinance` API, lazy `markets/market_hours.py` |
| 4 | **Imported by** | `bot_controller.py` (start), `slot_pressure_monitor.py` (`get_market_regime` only) |
| 5 | **Executed by** | `bot_controller.start_bot()`, `market_open_runner.sh`, `market_session_guard.py`, manual |
| 6 | **Called by live_bot** | N/A (self) |
| 7 | **Influences BUY** | **YES** — STRONG BUY + score≥80 + BULL regime + ticker session open + sizing |
| 8 | **Influences SELL** | **YES** — TAKE PROFIT, +5%/-3% rules, TEST_SELL_MODE |
| 9 | **Score/risk/sizing/session** | **YES** — internal RSI/SMA50 score; SPY SMA200 regime; dynamic cash sizing; per-ticker session |
| 10 | **Adapter** | None — no adapter layer |
| 11 | **Classification** | **CONNECTED_TO_LIVE** |

**Subprocess:** `position_intelligence.py` (post `generate_signals()` — nu influențează BUY/SELL în același cycle)

**Not imported:** `research_core`, `tae_*`, `core/trades.py`, `config/settings.py` (uses inline constants)

---

### 3.2 Dashboard Streamlit (`dashboard_v2.py`)

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `dashboard_v2.py`, `data/storage.py`, `core/portfolio.py`, `core/market_regime.py`, `config/settings.py`, `bot_controller.py` (start/stop) |
| 2 | **Produces** | None (UI only; export buttons for CSV/TXT download) |
| 3 | **Consumes** | **40+ legacy CSV/TXT/JSON** — `portfolio.csv`, `live_signals.csv`, `signals.csv`, `alerts_log.csv`, `bot_status.txt`, `position_intelligence_*`, allocator/strategic/*.csv, `daily_intelligence_report.txt`, etc. **Zero `tae_*.json`** |
| 4 | **Imported by** | None (Streamlit entry) |
| 5 | **Executed by** | `bot_controller.start_dashboard()`, manual `streamlit run dashboard_v2.py`, port 8501 |
| 6 | **Called by live_bot** | NO |
| 7 | **Influences BUY** | NO (display only; can start bot via UI) |
| 8 | **Influences SELL** | NO |
| 9 | **Score/risk/sizing/session** | Display only — reads regime/positions for UI |
| 10 | **Adapter** | None |
| 11 | **Classification** | **CONNECTED_TO_LIVE** (ops/monitor; reads live artifacts) |

---

### 3.3 Health Checks (`tae_quick_health_check.py` + runtime)

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `tae_quick_health_check.py`, `research_core/runtime/quick_health_wrapper.py`, `quick_health_report.py`, `runtime_health.py`, `ecosystem_state.py` |
| 2 | **Produces** | `tae_quick_health_check.json`, `tae_quick_health_check.txt` |
| 3 | **Consumes** | `tae_runtime_foundation.json`, `tae_ecosystem_orchestrator.json`, `bot_status.txt`, `bot_output.log`, `live_signals.csv`, `portfolio.csv` (mtime/read-only), optional layer reports, `process_health.json` |
| 4 | **Imported by** | `tae_full_ecosystem_run.py` (pre/post step) |
| 5 | **Executed by** | `python3 tae_quick_health_check.py`, ecosystem run step 1/last |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO — read-only observation |
| 10 | **Adapter** | `RuntimeAdapter` (`research_core/integration_adapters/runtime_adapter.py`) |
| 11 | **Classification** | **REPORT_ONLY** |

**Explicit constraint in code:** "Does not start/stop bot"

---

### 3.4 Market Session Guard

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `market_session_guard.py`, `market_session_guard.sh`, `markets/market_hours.py`, `markets/market_config.py`, `bot_controller.py`, `awake_guard.sh` |
| 2 | **Produces** | `market_session_guard.log`, `startup_ops.log` (via bot_controller), `awake_guard.log` |
| 3 | **Consumes** | Market timezone config only |
| 4 | **Imported by** | None (script entry) |
| 5 | **Executed by** | Cron `*/10`, `startup_runner.sh`, `market_open_runner.sh`, `@reboot` (if installed) |
| 6 | **Called by live_bot** | NO |
| 7 | **Influences BUY** | NO — only ensures bot **process** is RUNNING when any market open |
| 8 | **Influences SELL** | NO |
| 9 | **Session gate** | Indirect — live_bot has its own per-ticker session check inside trading loop |
| 10 | **Adapter** | None |
| 11 | **Classification** | **CONNECTED_TO_LIVE** (process ops only, not trading logic) |

**Related (monitor only):** `market_session_monitor.py` → `market_session_history.csv` — **ORPHAN** relative to live_bot

---

### 3.5 Historical Execution

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/strategy_simulation/historical_execution_engine.py`, `historical_backtest_runner.py`, `historical_execution_report.py`, `tae_phase10_historical_execution_demo.py`, `tae_historical_execution_runner.py` |
| 2 | **Produces** | `tae_historical_execution.json`, `.txt`, `tae_historical_execution_checkpoint.json` |
| 3 | **Consumes** | `tae_historical_research.json`, `tae_strategy_simulation.json`, `tae_strategy_discovery.json`, yfinance OHLCV |
| 4 | **Imported by** | Demos, runner only |
| 5 | **Executed by** | `tae_phase10_historical_execution_demo.py`, `tae_historical_execution_runner.py` |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO — backtest simulation only |
| 10 | **Adapter** | None dedicated |
| 11 | **Classification** | **REPORT_ONLY** |

---

### 3.6 Historical Results Analysis

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/strategy_simulation/historical_results_analysis.py`, `historical_results_analysis_report.py`, `tae_historical_results_analysis_demo.py` |
| 2 | **Produces** | `tae_historical_results_analysis.json`, `.txt` |
| 3 | **Consumes** | `tae_historical_execution.json`, `tae_strategy_discovery.json` |
| 4 | **Imported by** | Demo only |
| 5 | **Executed by** | `tae_historical_results_analysis_demo.py` |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO |
| 10 | **Adapter** | None |
| 11 | **Classification** | **REPORT_ONLY** |

**Downstream consumer:** None in repo (meta intelligence does NOT read this file)

---

### 3.7 Strategy Discovery

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/strategy_discovery/*` (feature_library, hypothesis_generator, candidate_builder, report), `tae_phase10_strategy_discovery_demo.py` |
| 2 | **Produces** | `tae_strategy_discovery.json`, `.txt` (100 DISCOVERY_* strategies) |
| 3 | **Consumes** | Internal feature library only |
| 4 | **Imported by** | Simulation engine, historical research/execution/analysis (read discovery registry) |
| 5 | **Executed by** | `tae_phase10_strategy_discovery_demo.py` |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO |
| 10 | **Adapter** | None |
| 11 | **Classification** | **REPORT_ONLY** (research input for simulation pipeline) |

---

### 3.8 Continuous Strategy Ranking

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/strategy_evolution/continuous_ranking_engine.py`, `continuous_ranking_report.py`, `tae_phase8_continuous_ranking_engine_demo.py` |
| 2 | **Produces** | `tae_continuous_strategy_ranking.json`, `.txt` |
| 3 | **Consumes** | `tae_parallel_paper_validation.json`, `tae_candidate_strategy_registry.json` |
| 4 | **Imported by** | `daily_runner.py`, `meta_intelligence_engine.py`, `meta_evolution_engine.py`, `promotion_gate.py`, `paper_tracking_log.py`, `StrategyAdapter` |
| 5 | **Executed by** | `StrategyEvolutionDailyRunner` step 3, standalone demo |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO — ranks paper candidates vs LIVE_BASELINE |
| 10 | **Adapter** | `StrategyAdapter` (orchestrator read path) |
| 11 | **Classification** | **REPORT_ONLY** |

---

### 3.9 Candidate Strategy Registry

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/strategy_evolution/candidate_registry.py`, `candidate_report.py`, `tae_phase8_candidate_strategy_registry_demo.py` |
| 2 | **Produces** | `tae_candidate_strategy_registry.json`, `.txt` |
| 3 | **Consumes** | `portfolio.csv` (read-only FIFO analysis), `tae_evidence_engine_report.json`, `tae_continuous_strategy_simulation_lab.json`, `tae_independent_double_entry_verification.json` |
| 4 | **Imported by** | `daily_runner.py`, ranking engine, meta intelligence/evolution, governance, adapters |
| 5 | **Executed by** | Daily runner step 1, demo |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO — registers candidates from evidence/simulation; reads live trades for metrics only |
| 10 | **Adapter** | `StrategyAdapter` |
| 11 | **Classification** | **REPORT_ONLY** |

---

### 3.10 Meta Intelligence

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/meta_intelligence/meta_intelligence_engine.py`, `meta_intelligence_report.py`, `meta_intelligence_constants.py`, `tae_phase10_meta_intelligence_demo.py` |
| 2 | **Produces** | `tae_meta_intelligence.json`, `.txt` |
| 3 | **Consumes** | `tae_runtime_foundation.json`, `tae_ecosystem_orchestrator.json`, `tae_strategy_evolution_daily_runner.json`, `tae_candidate_strategy_registry.json`, `tae_continuous_strategy_ranking.json`, `tae_strategic_performance_audit.json`, `tae_paper_tracking_log.json`, `tae_daily_intelligence_report.json` |
| 4 | **Imported by** | `meta_evolution_engine.py`, `recommendation_outcome_engine.py` |
| 5 | **Executed by** | `tae_phase10_meta_intelligence_demo.py` (NOT in daily ecosystem run pipeline) |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO — `REVIEW_ONLY` observations |
| 10 | **Adapter** | None (reads canonical JSON directly) |
| 11 | **Classification** | **REPORT_ONLY** |

---

### 3.11 Meta Evolution

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/meta_intelligence/meta_evolution_engine.py`, `meta_evolution_report.py`, `tae_phase10_meta_evolution_demo.py` |
| 2 | **Produces** | `tae_meta_evolution.json`, `.txt` |
| 3 | **Consumes** | `tae_meta_intelligence.json` + same canonical inputs as meta intelligence |
| 4 | **Imported by** | None |
| 5 | **Executed by** | `tae_phase10_meta_evolution_demo.py` |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO — recommendations require human review |
| 10 | **Adapter** | None |
| 11 | **Classification** | **REPORT_ONLY** |

---

### 3.12 Evidence Engine

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/evidence_engine/evidence_registry.py`, `evidence_report.py`, supporting modules, `tae_phase7_evidence_engine_demo.py` |
| 2 | **Produces** | `tae_evidence_engine_report.json`, `.txt` |
| 3 | **Consumes** | Multiple prior audit JSONs (`tae_closed_freeze_*`, `tae_profit_attribution.json`, simulation lab, etc.) |
| 4 | **Imported by** | `EcosystemOrchestrator`, `EvidenceIntegrationGate`, `CandidateStrategyRegistry`, `ecosystem_state.py`, adapters |
| 5 | **Executed by** | `tae_full_ecosystem_run.py` step, demo |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO |
| 10 | **Adapter** | `EvidenceAdapter`, `IntegrationGateAdapter` |
| 11 | **Classification** | **REPORT_ONLY** |

**Gate consumer:** `integration_layer/evidence_gate.py` → `tae_evidence_integration_gate.json` — still no live path

---

### 3.13 Event Memory (X.6A)

| # | Field | Value |
|---|-------|-------|
| 1 | **Source files** | `research_core/market_intelligence/event_schema.py`, `event_memory_store.py`, `event_memory_report.py`, `tae_phase11_event_memory_demo.py` |
| 2 | **Produces** | `tae_event_memory.json`, `.txt` (0 events) |
| 3 | **Consumes** | None (empty scaffold) |
| 4 | **Imported by** | Demo only |
| 5 | **Executed by** | `tae_phase11_event_memory_demo.py` |
| 6 | **Called by live_bot** | NO |
| 7–9 | **BUY/SELL/score** | NO |
| 10 | **Adapter** | None |
| 11 | **Classification** | **SCAFFOLD_ONLY** |

---

### 3.14 Adapters / Connectors / Loaders / Readers

| Adapter | Module | Reads | Serves | Live? |
|---------|--------|-------|--------|-------|
| `AccountingAdapter` | `integration_adapters/accounting_adapter.py` | Accounting reports | Orchestrator contract | NO |
| `EvidenceAdapter` | `evidence_adapter.py` | `tae_evidence_engine_report.json` | Orchestrator | NO |
| `SimulationAdapter` | `simulation_adapter.py` | Simulation lab reports | Orchestrator | NO |
| `StrategyAdapter` | `strategy_adapter.py` | Daily runner + registry + ranking + gate + paper | Orchestrator | NO |
| `IntegrationGateAdapter` | `integration_gate_adapter.py` | Evidence integration gate | Orchestrator | NO |
| `OrchestratorAdapter` | `orchestrator_adapter.py` | Orchestrator report | Runtime | NO |
| `RuntimeAdapter` | `runtime_adapter.py` | Runtime foundation | Quick health | NO |
| Registry | `adapter_registry.py` | All above | `tae_adapter_registry.json` | NO |

**EcosystemStateLoader** (`research_core/runtime/ecosystem_state.py`) — central JSON loader for runtime/orchestrator; **no live_bot connection**.

**Integration rule (documented):** `Module A → Contract → Adapter → Canonical JSON → Adapter → Module B` — entirely within research/report layer.

---

## 4. Artifact Flow Map (tae_* canonical)

```
portfolio.csv (LIVE writes)
    │
    ├──[read-only]──► candidate_registry ──► tae_candidate_strategy_registry.json
    ├──[read-only]──► paper_tracking_log
    ├──[read-only]──► performance audits
    ├──[read-only]──► quick_health_check
    └──[read-only]──► dashboard_v2.py

tae_evidence_engine_report.json
    └──► candidate_registry, evidence_gate, orchestrator, meta (indirect)

tae_candidate_strategy_registry.json
    └──► parallel_paper_validator, continuous_ranking, promotion_gate, meta_*

tae_continuous_strategy_ranking.json
    └──► promotion_gate, paper_tracking, meta_intelligence, meta_evolution

tae_meta_intelligence.json
    └──► meta_evolution, recommendation_outcome

tae_strategy_discovery.json
    └──► simulation, historical_research, historical_execution, historical_results_analysis
         (research chain only — dead end vs live)

tae_historical_execution.json
    └──► historical_results_analysis ONLY

tae_event_memory.json
    └──► (no consumer)
```

---

## 5. Scheduled Runners & Process Topology

| Runner | Schedule | Starts bot | Starts dashboard | Touches trading |
|--------|----------|------------|------------------|-----------------|
| `startup_runner.sh` | `@reboot` / LaunchAgent | Via guard | Via guard | NO |
| `market_session_guard.sh` | `*/10` weekdays | YES if market open | YES if market open | NO |
| `market_open_runner.sh` | 09:50 weekdays | YES | YES | NO |
| `market_close_runner.sh` | 23:15 weekdays | NO (kills caffeinate) | NO | NO |
| `daily_intelligence_runner.py` | */30 | NO | NO | NO |
| `live_bot.py` loop | 60s when running | — | — | **YES (PAPER)** |
| `tae_full_ecosystem_run.py` | Manual / cron optional | NO | NO | NO |

---

## 6. Alternate Live Path (not active via bot_controller)

| Module | Notes | Classification |
|--------|-------|----------------|
| `live_bot_v5_1.py` | Uses `core/trades.py`, `config/settings.py`, per-ticker session — **not started by bot_controller** | **ORPHAN** (alternate implementation) |
| `live_signal_refresh.py` | Imports `live_bot_v5_1.manage_portfolio` | **ORPHAN** |
| `slot_pressure_monitor.py` | Imports `live_bot.get_market_regime`; reads `portfolio.csv` | **REPORT_ONLY** monitor |

**Active bot entrypoint per `bot_controller.py`:** `live_bot.py` (monolith)

---

## 7. Dashboard vs TAE JSON Gap

`dashboard_v2.py` reads **zero** `tae_*.json` files. Entire Phase VIII–X canonical output is **invisible in dashboard UI**. Dashboard shows legacy allocator/strategic/committee CSV/TXT ecosystem.

Quick health and ecosystem run **do** read `tae_*` — but only as reports.

---

## 8. Score / Risk / Session — Who Owns What

| Concern | Live owner | Research owner |
|---------|------------|----------------|
| Entry score (RSI/SMA50) | `live_bot.py` inline | Discovery/simulation (disconnected) |
| MIN_SCORE_TO_BUY (=80) | `live_bot.py` constant | N/A |
| Market regime (SPY SMA200) | `live_bot.py` | `core/market_regime.py` (dashboard/v5_1 only) |
| Session gate | `markets/market_hours.py` via live_bot | `market_session_guard` (process only) |
| Position sizing | `live_bot.get_dynamic_trade_size()` | `core/risk.py` (v5_1 only) |
| Strategy ranking score | — | `continuous_ranking_engine.py` |
| Evidence confidence | — | `evidence_registry.py` |

---

## 9. Import Graph Summary (live_bot isolation)

```
live_bot.py imports:
  os, time, datetime, pathlib, pandas, requests, yfinance
  (lazy) markets.market_hours

live_bot.py does NOT import:
  research_core.*, core.*, config.settings, integration_layer.*,
  bot_controller, dashboard, any tae_* consumer

research_core does NOT import live_bot (except slot_pressure_monitor partial)
```

---

## 10. Verdict Table (requested modules)

| Module | Classification | BUY | SELL | Live called |
|--------|----------------|-----|------|-------------|
| live_bot.py | CONNECTED_TO_LIVE | YES | YES | — |
| dashboard_v2.py | CONNECTED_TO_LIVE | NO* | NO* | NO |
| health checks | REPORT_ONLY | NO | NO | NO |
| market session guard | CONNECTED_TO_LIVE (ops) | NO | NO | NO |
| historical execution | REPORT_ONLY | NO | NO | NO |
| historical results analysis | REPORT_ONLY | NO | NO | NO |
| strategy discovery | REPORT_ONLY | NO | NO | NO |
| continuous strategy ranking | REPORT_ONLY | NO | NO | NO |
| candidate strategy registry | REPORT_ONLY | NO | NO | NO |
| meta intelligence | REPORT_ONLY | NO | NO | NO |
| meta evolution | REPORT_ONLY | NO | NO | NO |
| evidence engine | REPORT_ONLY | NO | NO | NO |
| event memory | SCAFFOLD_ONLY | NO | NO | NO |
| adapters | REPORT_ONLY | NO | NO | NO |

\*Dashboard can start/stop bot process; does not alter trading rules.

---

## MISSING LINKS ONLY

> Propuneri de legătură lipsă — **nu implementate**, doar constatări pentru arhitect.

1. **Live bot ↔ TAE strategy pipeline** — No bridge from `tae_continuous_strategy_ranking.json` or `DISCOVERY_*` strategies to `watchlist.txt` or live_bot entry rules. Ranking conclusions never reach live execution.

2. **Live bot ↔ Meta intelligence** — `tae_meta_intelligence.json` / `tae_meta_evolution.json` not consumed by live_bot, dashboard, or session guard. Promotion/retirement recommendations have no automated or manual UI surfacing in dashboard.

3. **Historical results ↔ Meta intelligence** — `tae_historical_results_analysis.json` (robust/weak shortlists) has zero downstream consumer in repo.

4. **Event memory ↔ anything** — `tae_event_memory.json` is scaffold-only; no ingestion, no psychology engine, no live session context.

5. **Dashboard ↔ TAE canonical JSON** — Dashboard reads legacy CSV/TXT only; operator cannot see `tae_*` reports without separate tools.

6. **Evidence gate ↔ Live bot** — `tae_evidence_integration_gate.json` explicitly blocks live deployment; no approved path exists even for paper-mode rule import into live_bot.

7. **Meta intelligence ↔ Daily ecosystem run** — Meta intelligence/evolution demos are **outside** `tae_full_ecosystem_run.py` pipeline; must be run manually.

8. **live_bot_v5_1 ↔ bot_controller** — Modular bot with `core/trades.py` exists but is not the started script; creates dual-codepath confusion.

9. **Recommendation outcome ↔ Live** — `tae_recommendation_outcome.json` (X.2C) not wired to dashboard or live ops feedback.

10. **StrategyAdapter ↔ live_bot** — Adapter serves orchestrator JSON only; no runtime hook to apply strategy evolution state to live watchlist or thresholds.

---

*End of audit. No files modified except this report. No implementation performed.*
