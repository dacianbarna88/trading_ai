# TAE Indirect Integration Audit — X.7 Fix

**Date:** 2026-06-29  
**Mode:** AUDIT ONLY | NO CODE CHANGES  
**Scope:** Indirect paths TAE → LIVE via adapters, bridges, exports, registries, ranking, and shared artifacts

---

## Executive summary

The prior audit correctly found **no direct import** of `research_core` in `live_bot.py`. This correction audit traces **artifact read/write chains** and finds:

| Question | Finding |
|----------|---------|
| Does TAE automatically influence LIVE BUY/SELL today? | **No** — no automated write path from `tae_*.json` / `research_core` into files consumed by `live_bot.py` for trading decisions |
| Does LIVE influence TAE? | **Yes (read-only)** — `portfolio.csv` and `live_signals.csv` are **inputs** to multiple TAE audit modules |
| Are there legacy non-TAE indirect chains? | **Yes** — orphan `live_bot_v5_1` / `research/signals.py` path, `signal_to_decision_engine.py` → `decision_registry.csv`, manual `watchlist.txt` updaters |
| Adapters export to runtime? | **No** — `research_core/integration_adapters/*` produce/consume `tae_*.json` only; orchestrator reads via `StrategyAdapter`, never writes live artifacts |

**Verdict (see §Final):** TAE is **REPORT_ONLY** + **ADVISORY_ONLY** relative to live trading. **No DIRECT or INDIRECT automated TAE→LIVE execution bridge** was found. Reverse observation chains (LIVE→TAE) exist and are documented below.

---

## Artifact ownership matrix

### 1. `live_signals.csv`

| Role | Module | TAE? |
|------|--------|------|
| **WRITES** | `live_bot.py` (`generate_signals()` → `df.to_csv`) | No |
| **WRITES** | `research/signals.py` (used by `live_bot_v5_1.py`, `live_signal_refresh.py`) | No |
| **READS** | `dashboard_v2.py` (display) | No |
| **READS** | `signal_to_decision_engine.py` | No |
| **READS** | `research_core/runtime/quick_health_wrapper.py` (mtime/freshness only) | Yes |
| **READS** | `research_core/full_ecosystem/full_ecosystem_run.py` (freshness metadata) | Yes |
| **READS** | `research_core/performance/strategic_performance_auditor.py` | Yes |
| **READS** | `research_core/score_decomposition/score_decomposition_analyzer.py` | Yes |
| **READS** | `research_core/entry_analysis/counterfactual_entry.py` | Yes |
| **READS** | Legacy audits (`threshold_test_simulator.py`, `adaptive_strategic_risk.py`, etc.) | No |

**TAE write to `live_signals.csv`:** **None found** in `research_core/`.

---

### 2. `decision_registry.csv`

| Role | Module | TAE? |
|------|--------|------|
| **WRITES** | `decision_registry.py` (from `adaptive_decision_guard_summary.txt`) | No |
| **WRITES** | `signal_to_decision_engine.py` (from `live_signals.csv`) | No |
| **WRITES** | `enrich_decision_registry.py`, `entry_price_filler.py`, `outcome_evaluator.py`, `feedback_update_engine.py`, etc. | No |
| **READS** | `dashboard_v2.py` (display tail 50) | No |
| **READS** | Legacy learning engines (`learning_health_engine.py`, `confidence_calibration_engine.py`, …) | No |
| **READS** | `research_core/**` | **None** |

**TAE involvement:** **NONE**. `decision_registry.csv` is a legacy PAPER_ONLY registry chain, not connected to TAE or `live_bot.py`.

---

### 3. `portfolio.csv`

| Role | Module | TAE? |
|------|--------|------|
| **WRITES (LIVE)** | `live_bot.py` (`save_portfolio`, `manage_portfolio`, `update_portfolio_prices`) | No |
| **WRITES (repair tools)** | `tools/recompute_realized_pnl.py --apply`, `core/portfolio_prices.py` | No |
| **READS (LIVE)** | `live_bot.py` (BUY/SELL state) | No |
| **READS (dashboard)** | `dashboard_v2.py`, `data/storage.py` | No |
| **READS (TAE, read-only)** | 30+ modules: `parallel_paper_validator`, `candidate_registry`, `independent_double_entry`, `strategic_performance_auditor`, `daily_runner`, orchestrator, full ecosystem, meta intelligence constants, etc. | Yes |
| **WRITES (TAE)** | **None** — all TAE modules treat `portfolio.csv` as protected/read-only; `research_core/recalibration` mentions optional `--apply` in text but defers to `tools/recompute_realized_pnl.py`, not TAE auto-run |

---

### 4. `config/settings.py`

| Role | Module | TAE? |
|------|--------|------|
| **WRITES** | **None automated** in repo | — |
| **READS (LIVE path)** | `live_bot_v5_1.py`, `research/signals.py`, `core/entry_filter.py`, `core/risk.py` | No |
| **NOT READ by canonical live bot** | `live_bot.py` uses **inline constants** (`MIN_SCORE_TO_BUY = 80`, etc.) — **does not import** `config/settings.py` | — |
| **READS (TAE)** | Protected-file mtime checks only (`quick_health_wrapper`, orchestrator, daily_runner, …) | Yes (guard only) |

**TAE modification of thresholds via `settings.py`:** **None**.

---

## Explicit checks (1–12)

| # | Check | Result |
|---|-------|--------|
| 1 | Who writes `live_signals.csv`? | **`live_bot.py`** (runtime). Orphan: `research/signals.py` via `live_bot_v5_1.py` / `live_signal_refresh.py` |
| 2 | Who reads `live_signals.csv`? | Dashboard, legacy engines, TAE auditors (read-only), quick health |
| 3 | Who writes `decision_registry.csv`? | Legacy paper registry scripts — **not TAE, not live_bot** |
| 4 | Who reads `decision_registry.csv`? | Dashboard + legacy learning engines — **not live_bot, not research_core** |
| 5 | Who writes `portfolio.csv`? | **`live_bot.py`** (+ manual repair tools) |
| 6 | Who reads `portfolio.csv`? | **`live_bot.py`**, dashboard, TAE (read-only audits) |
| 7 | Any `tae_*.json` → file consumed by `live_bot.py`? | **No** — `live_bot.py` reads: `watchlist.txt`, yfinance, `markets/market_hours.py`; writes CSV/logs only |
| 8 | Dashboard regenerates signals? | **No** — starts/stops `live_bot.py` via `bot_controller`; TAE tab is read-only JSON; no subprocess to TAE demos or signal scripts |
| 9 | `market_scanner.py` in live runtime? | **No** for canonical `live_bot.py`. Used by **`live_bot_v5_1.py`** (orphan) and can write `watchlist.txt` if run manually |
| 10 | `telegram_bot.py` consumes TAE signals? | **No** — reads legacy **`signals.csv`**, not `live_signals.csv` or any `tae_*.json` |
| 11 | Adapters export toward runtime? | **No** — adapters read `tae_*.json`, validate contracts, feed orchestrator reports; outputs remain `tae_*.json` / `.txt` |
| 12 | TAE modifies scoring/risk/sizing/session gate indirectly? | **No automated path**. Recommendations exist in JSON (`tae_meta_evolution.json`, `tae_strategy_recommendations.json`, `tae_implementation_patch.json`) for **human review only** |

---

## Documented chains

Format: SOURCE → PRODUCED → ADAPTER → CONSUMED → LIVE_CONSUMER → IMPACT

---

### Chain A — Canonical LIVE signal loop (not TAE)

```
SOURCE_MODULE:     live_bot.py
PRODUCED_ARTIFACT: live_signals.csv, portfolio.csv, alerts_log.csv
ADAPTER:           (none)
CONSUMED_ARTIFACT: watchlist.txt (read), yfinance (API)
LIVE_CONSUMER:     live_bot.py (manage_portfolio BUY/SELL)
IMPACT:            BUY | SELL
```

Sub-chain after each cycle:

```
SOURCE_MODULE:     live_bot.py (subprocess)
PRODUCED_ARTIFACT: position_intelligence_report.csv
ADAPTER:           (none)
CONSUMED_ARTIFACT: portfolio.csv (read)
LIVE_CONSUMER:     dashboard_v2.py (display only)
IMPACT:            DASHBOARD_ONLY
```

---

### Chain B — LIVE → TAE observation (reverse direction)

```
SOURCE_MODULE:     live_bot.py
PRODUCED_ARTIFACT: live_signals.csv, portfolio.csv
ADAPTER:           (none — direct file read)
CONSUMED_ARTIFACT: tae_quick_health_check.json, tae_strategic_performance_audit.json,
                   tae_score_decomposition_anomaly.json, tae_full_ecosystem_run.json, …
LIVE_CONSUMER:     (none — TAE does not feed back)
IMPACT:            NONE (on live trading)
```

**Note:** This is LIVE output used as TAE **input**. It does not change BUY/SELL.

---

### Chain C — TAE ranking pipeline (internal JSON only)

```
SOURCE_MODULE:     research_core/strategy_evolution/daily_runner.py
PRODUCED_ARTIFACT: tae_strategy_evolution_daily_runner.json
ADAPTER:           research_core/integration_adapters/strategy_adapter.py
CONSUMED_ARTIFACT: tae_candidate_strategy_registry.json,
                   tae_continuous_strategy_ranking.json,
                   tae_strategy_promotion_gate.json,
                   tae_paper_tracking_log.json
LIVE_CONSUMER:     research_core/orchestrator/ecosystem_orchestrator.py
                   → tae_ecosystem_orchestrator.json
IMPACT:            REPORT_ONLY
```

No step writes `watchlist.txt`, `live_signals.csv`, or `portfolio.csv`.

---

### Chain D — TAE meta / advisory layer

```
SOURCE_MODULE:     research_core/meta_intelligence/meta_intelligence_engine.py
PRODUCED_ARTIFACT: tae_meta_intelligence.json
ADAPTER:           (internal read of ranking/registry JSON)
CONSUMED_ARTIFACT: tae_meta_evolution.json (recommendations)
LIVE_CONSUMER:     dashboard_v2.py (TAE Intelligence Reports tab)
IMPACT:            ADVISORY_ONLY | DASHBOARD_ONLY
```

Promotion recommendations explicitly state human review; no export to live artifacts.

---

### Chain E — TAE full ecosystem daily run

```
SOURCE_MODULE:     tae_full_ecosystem_run.py → FullEcosystemRunner
PRODUCED_ARTIFACT: tae_full_ecosystem_run.json + canonical tae_* step outputs
ADAPTER:           QuickHealthWrapper, StrategyAdapter, EvidenceIntegrationGate
CONSUMED_ARTIFACT: portfolio.csv, live_signals.csv (read-only freshness checks)
LIVE_CONSUMER:     (none)
IMPACT:            REPORT_ONLY
```

Protected-file guard confirms `live_bot.py`, `portfolio.csv`, `config/settings.py` mtimes unchanged during run.

---

### Chain F — Legacy paper registry (not TAE)

```
SOURCE_MODULE:     live_bot.py
PRODUCED_ARTIFACT: live_signals.csv
ADAPTER:           signal_to_decision_engine.py (manual/off-schedule)
CONSUMED_ARTIFACT: decision_registry.csv
LIVE_CONSUMER:     dashboard_v2.py, learning_* engines
IMPACT:            REGISTRY_ONLY | DASHBOARD_ONLY
```

**`live_bot.py` does not read `decision_registry.csv`.** No BUY/SELL impact.

---

### Chain G — Orphan v5.1 / settings path (not TAE)

```
SOURCE_MODULE:     live_bot_v5_1.py (NOT started by bot_controller when live_bot.py exists)
PRODUCED_ARTIFACT: live_signals.csv via research/signals.py
ADAPTER:           config/settings.py (MIN_SCORE_TO_BUY=90), core/entry_filter, core/risk
CONSUMED_ARTIFACT: watchlist.txt (may be updated by research/market_scanner.py)
LIVE_CONSUMER:     manage_portfolio in v5_1
IMPACT:            BUY | SELL (only if v5_1 run manually — orphaned)
```

**Not TAE.** Documented because it is a real indirect settings→signals→portfolio chain in the repo.

---

### Chain H — market_scanner → watchlist (manual, not TAE)

```
SOURCE_MODULE:     research/market_scanner.py (or auto_watchlist.py, universe_from_candidates.py)
PRODUCED_ARTIFACT: watchlist_candidates.csv → watchlist.txt
ADAPTER:           (none)
CONSUMED_ARTIFACT: watchlist.txt
LIVE_CONSUMER:     live_bot.py (load_watchlist)
IMPACT:            BUY | SELL (indirect — ticker universe only; thresholds still inline in live_bot)
```

**Not TAE.** Requires separate manual/scheduled execution; not wired to TAE demos or dashboard.

---

### Chain I — Dashboard runtime control (no TAE feed)

```
SOURCE_MODULE:     dashboard_v2.py / market_session_guard.py
PRODUCED_ARTIFACT: bot_pid.txt, bot_status.txt (via bot_controller)
ADAPTER:           bot_controller.start_bot()
CONSUMED_ARTIFACT: live_bot.py process
LIVE_CONSUMER:     live_bot.py
IMPACT:            BUY | SELL (indirect — starts live loop; TAE JSON not involved)
```

Dashboard **displays** TAE reports and **starts** live bot independently. No TAE artifact is passed into the bot start command.

---

### Chain J — Quick health invokes morning script (monitoring only)

```
SOURCE_MODULE:     research_core/runtime/quick_health_wrapper.py
PRODUCED_ARTIFACT: tae_quick_health_check.json
ADAPTER:           subprocess → tools/morning_control_room.sh
CONSUMED_ARTIFACT: bot_status.txt, live_signals.csv, portfolio.csv, tae_*.json (existence checks)
LIVE_CONSUMER:     (none — read-only shell audit)
IMPACT:            REPORT_ONLY
```

---

### Chain K — Implementation patch (human gate)

```
SOURCE_MODULE:     research_core/evolution/implementation_patch.py
PRODUCED_ARTIFACT: tae_implementation_patch.json, tae_implementation_patch.txt
ADAPTER:           (none automated)
CONSUMED_ARTIFACT: (potential manual apply to live_bot.py / core/* — NOT implemented in repo)
LIVE_CONSUMER:     (none unless human edits files)
IMPACT:            ADVISORY_ONLY (designed); would be BUY|SELL only after manual merge
```

Code explicitly: *"Sprint A7 — no file writes to live trading code."*

---

## Adapters in `research_core/integration_adapters/`

| Adapter | Reads | Writes | Live export? |
|---------|-------|--------|--------------|
| `StrategyAdapter` | `tae_strategy_evolution_*.json`, ranking, registry, gate, paper log | `tae_adapter_report.json` (via audit) | **No** |
| `EvidenceAdapter` | `tae_evidence_engine_report.json` | tae reports | **No** |
| `AccountingAdapter` | accounting tae JSON | tae reports | **No** |
| `SimulationAdapter` | simulation lab JSON | tae reports | **No** |
| `IntegrationGateAdapter` | evidence integration gate | tae reports | **No** |
| `OrchestratorAdapter` / `RuntimeAdapter` | orchestrator/runtime JSON | tae reports | **No** |

`StrategyAdapter.load_strategy_state_for_orchestrator()` is consumed **only** by `ecosystem_orchestrator.py` and migration audit demos — not by `live_bot.py`.

---

## Scoring / risk / sizing / session gate

| Mechanism | live_bot.py source | TAE indirect influence? |
|-----------|---------------------|-------------------------|
| `MIN_SCORE_TO_BUY` | Inline `80` in `live_bot.py` | **No** — settings.py (90) unused by canonical bot |
| `MAX_POSITIONS`, trade sizing | Inline in `live_bot.py` | **No** |
| Market regime filter | Inline + yfinance SPY SMA200 | **No** |
| Per-ticker session gate | `markets/market_hours.is_ticker_market_open()` | **No TAE write**; guard scripts start bot when session open |
| `core/risk.py`, `core/entry_filter.py` | Used by v5_1 / research path only | **No** for canonical live_bot |

TAE modules **analyze** score anomalies (`tae_score_decomposition_anomaly.json`) and produce **recommendations** — they do not push threshold updates to any live consumer.

---

## Startup / scheduling

| Script | Starts live? | Runs TAE? |
|--------|-------------|-----------|
| `startup_runner.sh` | Via `market_session_guard.py` → `start_bot()` | **No** |
| `market_session_guard.py` | `live_bot.py` + dashboard if market open | **No** |
| `bot_controller.py` | `live_bot.py` (fallback `telegram_bot.py`) | **No** |
| `tae_full_ecosystem_run.py` | **No** | Yes (report only) |

No launchd/cron wiring found that chains TAE full ecosystem → live bot in one automated pipeline.

---

## What the prior audit under-emphasized

1. **Reverse chains (LIVE→TAE)** are real and extensive — TAE reads live outputs for audits; this is not execution integration.
2. **Legacy parallel stack** (`live_bot_v5_1`, `signal_to_decision_engine`, `telegram_bot.py` + `signals.csv`) creates indirect live-adjacent flows **without TAE**.
3. **`watchlist.txt`** is the only practical indirect lever into canonical `live_bot.py` ticker universe — updaters are **not** TAE-connected.
4. **Dashboard** both displays TAE and can start live bot — correlation in UI, **not** data coupling.
5. **`tae_implementation_patch.json`** is a latent human-apply risk, not an automated bridge.

---

## Final verdict

| Category | Assessment |
|----------|------------|
| **1. DIRECT_LIVE_INTEGRATION** | **NONE** — `live_bot.py` does not import `research_core`; does not read any `tae_*.json` |
| **2. INDIRECT_LIVE_INTEGRATION (TAE→LIVE automated)** | **NONE** — no artifact chain from TAE JSON through adapter/registry into `live_signals.csv`, `portfolio.csv`, `watchlist.txt`, or `config/settings.py` consumed by canonical live bot |
| **3. ADVISORY_ONLY** | **YES** — meta intelligence, meta evolution, strategy recommendations, implementation patches, promotion gate verdicts (human review) |
| **4. REPORT_ONLY** | **YES** — bulk of Phase VIII–X pipeline; dashboard TAE tab + advisory index (X.7A/B) |

### Precise statement

> Absence of `research_core` imports in `live_bot.py` **does not alone prove isolation** — but artifact tracing confirms **no automated TAE→LIVE write path** for trading decisions.  
> **LIVE→TAE read-only observation** is active.  
> **Legacy non-TAE** chains can affect paper registry and (if manually run) orphan v5.1 / watchlist paths.

---

## Validation commands used (read-only)

```bash
rg 'live_signals\.csv' .
rg 'decision_registry\.csv' .
rg 'portfolio\.csv' research_core/
rg 'to_csv|write_text' research_core/
rg 'import research_core|from research_core' live_bot.py telegram_bot.py
rg 'market_scanner|tae_' live_bot.py bot_controller.py dashboard_v2.py
```

**No files modified during this audit.**

---

*End of TAE_INDIRECT_INTEGRATION_AUDIT_X7_FIX.md*
