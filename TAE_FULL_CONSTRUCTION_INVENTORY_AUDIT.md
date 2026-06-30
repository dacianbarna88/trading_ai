# TAE Full Construction Inventory Audit

**Date:** 2026-06-30  
**Mode:** AUDIT ONLY — no code modified  
**Machine-readable:** `tae_full_construction_inventory_audit.json`  
**Canonical references:** `PROJECT_BOOK.md`, `SESSION_START.md`, `TAE_GLOBAL_MARKET_INTELLIGENCE_PRE_AUDIT.md`

---

## Executive Verdict

| | |
|---|---|
| **Verdict** | **PARTIAL** |
| **Meaning** | Extensive TAE research, scanner, ranking, accounting, and governance infrastructure **exists and runs** — but canonical live runtime (`live_bot.py`) uses only `watchlist.txt` + inline scoring + advisory **BUY risk gate**. Global best-stocks pipeline is **built, stale, and report-only**. |

### Counts (key modules inventoried)

| Status | Count | Description |
|--------|------:|-------------|
| **CONNECTED** | 8 | Directly used by live runtime or dashboard ops |
| **REPORT_ONLY** | 28 | Produces artifacts; no live execution path |
| **ORPHAN / LEGACY** | 3 | `live_bot_v5_1.py`, direct watchlist writers |
| **DUPLICATE** | 1 | Parallel regional-strength models |
| **SCAFFOLD** | 1 | Event memory (blueprint only) |

**Repo scale:** ~653 Python files (excl. venv), 16 shell scripts, 98 root `tae_*.json`, 26 `TAE_*.md` docs.

---

## A. Runtime Canonical

### What runs in production

| Component | Entry point | Role |
|-----------|-------------|------|
| Live bot | `live_bot.py` via `bot_controller.py` | BUY/SELL paper execution |
| Dashboard | `streamlit run dashboard_v2.py :8501` | Observability + bot control |
| Session guard | `market_session_guard.py` (launchd/cron) | Auto-start when EU/UK/US open |
| Startup | `startup_runner.sh` | Login bootstrap |
| TAE ops | `tae_full_ecosystem_review.sh`, `tae_live_advisory_demo.py`, `tae_market_open_monitor.sh` | Report generation (manual/scheduled) |

### `live_bot.py` imports

| Type | Module |
|------|--------|
| Direct | `os`, `time`, `datetime`, `pathlib`, `pandas`, `requests`, `yfinance` |
| Conditional | `markets.market_hours` (session summary, per-ticker gate) |
| Conditional | `research_core.governance.live_advisory_runtime` |
| Conditional | `research_core.governance.shadow_validation_ledger` |
| Subprocess | `position_intelligence.py` (post-cycle, not imported) |

**Zero imports** from: scanners, ranking, discovery, `research/`, `strategic_intelligence/`, `sector_intelligence/`.

### Files read / written

| Direction | Files |
|-----------|-------|
| **Reads** | `watchlist.txt`, `portfolio.csv`, `alerts_log.csv`, `tae_live_advisory.json` |
| **Writes** | `portfolio.csv`, `live_signals.csv`, `alerts_log.csv`, `bot_output.log`, `bot_status.txt`, `tae_shadow_validation_events.csv` |
| **Does not read** | Any scanner CSV, ranking JSON, `watchlist_global.txt`, advisory index |

### BUY influences (all gates)

1. Universe: `watchlist.txt` only (+ open positions merged for scoring)
2. Signal: RSI/SMA50 score → `STRONG BUY` if score ≥ 80
3. Regime: SPY > SMA200 → `BULL` required (**strict** — `UNKNOWN` also blocks)
4. Session: per-ticker market open (`markets/market_hours.py`)
5. Capacity: max 12 positions, min $250 / max $2500 per trade
6. TAE: `RISK_ADVISORY` → `block_new_buy=True` (staleness fix applied)
7. **Not used:** global ranking, sector rotation, strategy discovery, dashboard scanner CSVs

### SELL influences

1. `TAKE PROFIT` signal (RSI > 70 in signal gen)
2. PnL ≥ +5% → take profit
3. PnL ≤ -3% → stop loss
4. `TEST_SELL_MODE` (disabled)
5. **Not used:** TAE `SELL_ADVISORY` (log-only), `position_intelligence.py`, market session gate

---

## B. Built But Not Connected to Runtime

### Scanner / global market intelligence

| Module | Artifact | Status |
|--------|----------|--------|
| `strategic_intelligence/global_market_scanner.py` | `global_market_scanner.csv` | REPORT_ONLY |
| `regional_strength_aggregator.py` | `regional_strength.csv` | REPORT_ONLY |
| `sector_intelligence/sector_rotation_scanner.py` | `sector_rotation.csv` | REPORT_ONLY |
| `research/multi_market_scanner.py` | `multi_market_candidates.csv` | REPORT_ONLY |
| `research/global_candidates.py` | `global_candidates.csv`, `watchlist_global.txt` | REPORT_ONLY |
| `research/global_opportunity_ranking.py` | `global_opportunity_ranking.csv` | REPORT_ONLY |
| `research/market_scanner.py` | `watchlist_candidates.csv` | REPORT_ONLY (53 US names) |
| `daily_gainers_*_research.py` | daily gainers CSVs | RESEARCH_ONLY |
| `momentum_universe_expansion_v13.py` | `us_expanded_universe.txt` | RESEARCH_ONLY |
| `tae_watchlist_proposal.py` | `tae_watchlist_proposal.json` | REPORT_ONLY (new) |

### TAE research pipeline (all REPORT_ONLY → advisory indirect)

| Layer | Key artifact |
|-------|--------------|
| Discovery | `tae_strategy_discovery.json`, `tae_discoveries.json` |
| Simulation | `tae_strategy_simulation.json` |
| Historical execution | `tae_historical_execution.json` (1600+ jobs) |
| Results analysis | `tae_historical_results_analysis.json` |
| Registry | `tae_candidate_strategy_registry.json` |
| Ranking | `tae_continuous_strategy_ranking.json` |
| Evidence | `tae_evidence_engine_report.json` |
| Meta | `tae_meta_intelligence.json` |
| Event memory | `tae_event_memory.json` (**SCAFFOLD**, 0 events) |
| Accounting | `tae_accounting_snapshot.json` |
| Orchestrator | `tae_ecosystem_orchestrator.json`, `tae_full_ecosystem_run.json` |

### Connected to live (only these)

| Module | Live effect |
|--------|-------------|
| `live_advisory_runtime.py` | BUY block on RISK_ADVISORY |
| `shadow_validation_ledger.py` | BUY event logging |
| `markets/market_hours.py` | Per-ticker session gate |
| `bot_controller.py` / `market_session_guard.py` | Process lifecycle |

---

## C. Best Stocks / Global Scanner

| Question | Answer |
|----------|--------|
| Do we have top stocks? | **Yes** — `global_opportunity_ranking.csv` (15 ranked equities) |
| Top N? | **Yes** — top 30 in `watchlist_global.txt`; top 53 in `watchlist_candidates.csv` (US S&P scan) |
| Best stocks selector? | **Yes** — `research/global_opportunity_ranking.py` |
| Watchlist promoter? | **No** — no governed auto-write to `watchlist.txt` |
| Watchlist proposal adapter? | **Yes** — `tae_watchlist_proposal.py` (10 recommended additions) |
| Global opportunity ranking? | **Yes** — primary ticker artifact |
| Universe scanner? | **Yes** — S&P500 + multi-market (US/EU/UK) |
| Daily gainers? | **Yes** — research scripts only |
| Momentum scanner? | **Partial** — spread across momentum v13 + daily gainers filter |
| Candidates produced | 15 global + 53 US scan = **63 deduplicated** in proposal |
| **Best artifact to use** | **`global_opportunity_ranking.csv`** (tickers) + **`tae_watchlist_proposal.json`** (governed proposal) |

**Staleness:** Global CSVs ~**161 hours** old; live bot artifacts fresh (~0h).

---

## D. Artifacts Matrix

| Artifact | Producer | Consumer | Fresh | Dashboard | Live bot |
|----------|----------|----------|-------|-----------|----------|
| `watchlist.txt` | manual / legacy scripts | **live_bot** | LIVE | No | **Yes** |
| `portfolio.csv` | live_bot | bot, accounting, TAE, UI | LIVE | Yes | **Yes** |
| `live_signals.csv` | live_bot | bot path, UI, advisory | LIVE | Yes | **Yes** |
| `tae_live_advisory.json` | advisory bridge | **live_bot**, UI | FRESH | Yes | **Yes** |
| `tae_shadow_validation_events.csv` | shadow ledger | reports, CC | RUNTIME | Yes | **Yes** |
| `global_opportunity_ranking.csv` | ranking script | dashboard, proposal | **STALE** | Yes | No |
| `global_candidates.csv` | global_candidates | dashboard, ranking | **STALE** | Yes | No |
| `watchlist_candidates.csv` | market_scanner | dashboard, proposal | **STALE** | Yes | No |
| `sector_rotation.csv` | sector scanner | benchmark only | **STALE** | **No** | No |
| `global_market_scanner.csv` | ETF scanner | regional chain | **STALE** | **No** | No |
| `tae_continuous_strategy_ranking.json` | ranking engine | advisory, CC | OK (~38h) | Yes | No |
| `tae_accounting_snapshot.json` | accounting | Performance tab, CC | FRESH | Yes | No |
| `tae_watchlist_proposal.json` | proposal adapter | *(none yet)* | FRESH | **No** | No |
| `tae_full_ecosystem_review.json` | ecosystem review | Command Center | FRESH | Yes | No |

**Gitignore:** All `*.csv`, `*.json` runtime outputs are gitignored — code tracked, artifacts local.

---

## E. Dashboard

### Shows already

- **TAE Command Center:** ecosystem review, accounting SSOT, advisory, shadow validation, strategy lab
- **Tab 1:** global candidates, opportunity ranking, watchlist scanner status, many allocator panels
- **Tab 7 Performance:** `tae_accounting_snapshot.json` (canonical PnL)
- **Tab 13:** all `tae_*.json` generic viewer
- **Live Bot tab:** start/stop, `live_signals.csv`, bot logs

### Does NOT show

- `global_market_scanner.csv`, `regional_strength.csv`, `sector_rotation.csv`
- `tae_watchlist_proposal.json`, `tae_market_open_monitor.json`
- `multi_market_candidates.csv`

### Stale / wrong sources in UI

- Tab 1 global/scanner CSVs (~7 days old vs live bot)
- `adaptive_allocation.json` — parallel regional model, not ETF scanner
- Daily Report / Portfolio tabs — legacy `portfolio.csv` PnL column path

### SSOT panels

- Command Center Financial → `tae_accounting_snapshot.json`
- Performance tab → same
- Command Center Advisory → `tae_live_advisory.json` + review

---

## F. Duplicates / Contradictions

| Area | Duplicate items | Resolution |
|------|-----------------|------------|
| Regional strength | ETF `regional_strength.csv` vs `adaptive_allocation.json` | Single macro SSOT for dashboard |
| Market hours | `markets/` vs `core/market_hours.py` | Canonical: `markets/` |
| Live bot | `live_bot.py` vs `live_bot_v5_1.py` | Canonical: `live_bot.py` only |
| PnL | portfolio column vs snapshot vs recompute vs double-entry | Snapshot SSOT for all UI |
| Watchlist expansion | auto_watchlist, universe_from_candidates, v5.1, proposal | Proposal adapter only |
| Strategy ranking | continuous vs hypothesis vs edge discovery | Different layers — document |

---

## G. Missing Links (real gaps only)

| Priority | Source → Target | Gap | Risk |
|----------|-----------------|-----|------|
| **CRITICAL** | `global_opportunity_ranking.csv` → `watchlist.txt` | No governed promotion | Best tickers never reach live |
| **CRITICAL** | `watchlist_global.txt` → `live_bot.py` | Only orphan v5.1 copies | Top-30 global never auto-applied |
| **HIGH** | `tae_watchlist_proposal.json` → dashboard | No panel | Operator can't review in UI |
| **HIGH** | Scanner CSV chain → scheduler | ~7d stale | Decisions on old market state |
| **HIGH** | Strategy ranking → ticker selection | Strategy-level only | Ranking can't expand universe alone |
| **HIGH** | Accounting snapshot → all dashboard PnL tabs | Legacy path remains | Contradictory PnL in UI |
| **MEDIUM** | Macro/sector CSVs → dashboard | Not displayed | Strategic context invisible |
| **MEDIUM** | Event memory blueprint → ingestion | Scaffold only | No psychology/event layer |
| **MEDIUM** | Shadow events → outcome attribution | Not built | Can't measure gate value |
| **LOW** | Position intelligence → SELL | Not consumed | By design — advisory only |

---

## H. Do Not Rebuild

| Exists — connect/display only |
|-------------------------------|
| Multi-market → global candidates → global opportunity ranking pipeline |
| `tae_watchlist_proposal.py` governance adapter |
| `continuous_ranking_engine` + `candidate_registry` |
| Historical execution engine (1600+ backtests complete) |
| Live advisory bridge + runtime + shadow ledger |
| ETF global scanner + sector rotation scanners |
| `accounting_snapshot.py` + execution integrity |
| `tae_full_ecosystem_review.py` |
| `markets/market_hours.py` session gate |

| Deprecate (don't extend) |
|--------------------------|
| `live_bot_v5_1.py` auto watchlist bridge |
| `auto_watchlist.py` / `universe_from_candidates.py` direct `watchlist.txt` write |
| `core/market_hours.py` duplicate |

---

## I. Recommended Roadmap

### 1. Immediate connect (no new engines)

1. Dashboard panel for `tae_watchlist_proposal.json` + `tae_market_open_monitor.json`
2. Schedule scanner refresh: `multi_market_scanner` → `global_candidates` → `global_opportunity_ranking`
3. Route all dashboard PnL to `tae_accounting_snapshot.json`
4. Display `sector_rotation.csv` + `regional_strength.csv` in macro panel

### 2. Audit needed

- Mark stale Tab 1 allocator panels deprecated or wire refresh
- X.10 shadow validation outcome attribution design
- Document `core/` vs `markets/` market hours

### 3. Cleanup

- Deprecate direct watchlist writers
- Reduce duplicate strategic/allocator dashboard panels

### 4. Future live integration (governed, not automatic)

- Operator-approved watchlist promotion workflow
- Event memory ingestion (Phase 2 blueprint)
- Position intelligence as SELL advisory hints (never auto-execute)

---

## Module Inventory Table (representative)

See `tae_full_construction_inventory_audit.json` → `modules[]` for full structured list.

| module_name | file_path | category | status | live_impact | dashboard_visible |
|-------------|-----------|----------|--------|-------------|-------------------|
| Live Bot | live_bot.py | runtime | CONNECTED | BUY/SELL spine | Yes |
| Live Advisory Runtime | research_core/governance/live_advisory_runtime.py | governance | CONNECTED | BUY risk gate | Yes |
| Shadow Validation Ledger | research_core/governance/shadow_validation_ledger.py | governance | CONNECTED | BUY logging | Yes |
| Global Opportunity Ranking | research/global_opportunity_ranking.py | scanner | REPORT_ONLY | None | Yes |
| Watchlist Proposal | tae_watchlist_proposal.py | watchlist | REPORT_ONLY | None | **No** |
| Continuous Strategy Ranking | research_core/strategy_evolution/continuous_ranking_engine.py | ranking | REPORT_ONLY | Advisory indirect | Yes |
| Event Memory Store | research_core/market_intelligence/event_memory_store.py | event_memory | SCAFFOLD | None | No |
| Live Bot v5.1 | live_bot_v5_1.py | runtime | ORPHAN | Legacy scanner bridge | No |
| Adaptive Allocation | generate_adaptive_allocation.py | allocator | DUPLICATE | None | Yes |

---

## Validation

```
python3 -m json.tool tae_full_construction_inventory_audit.json  → PASS
```

No code modified. Git status shows new audit artifacts only.

---

## Final Answer Summary

| Question | Answer |
|----------|--------|
| **General verdict** | **PARTIAL** — built extensively, live-connected minimally |
| **Connected modules** | **8** key (live bot, advisory runtime, shadow ledger, market hours, bot controller, session guard, dashboards) |
| **Report-only** | **28+** in inventory (majority of TAE + all scanners) |
| **Orphan/legacy** | **3** (v5.1 bot, direct watchlist writers) |
| **Global best stocks** | **Yes** — `global_opportunity_ranking.csv` + US `watchlist_candidates.csv` + `tae_watchlist_proposal.json` |
| **Top 5 missing links** | (1) ranking→watchlist promotion (2) watchlist_global→live (3) proposal→dashboard (4) scanner refresh schedule (5) accounting SSOT→all PnL tabs |
| **Do NOT rebuild** | Scanner chain, TAE ranking/registry/historical, advisory bridge, accounting kernel, session gate |
