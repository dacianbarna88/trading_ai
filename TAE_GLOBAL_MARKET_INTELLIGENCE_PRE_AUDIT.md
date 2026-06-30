# TAE Global Market Intelligence Pre-Audit

**Date:** 2026-06-30  
**Mode:** AUDIT ONLY — no code modified, no new modules  
**Scope:** Global / regional / sector / universe scanning, ranking, discovery, and live execution linkage

---

## Executive Conclusion

| Verdict | **PARTIAL — infrastructure EXISTS, live integration DOES NOT**

The ecosystem already contains **two substantial but disconnected stacks**:

1. **Legacy CSV scanner chain** — ETF global/regional intelligence, sector rotation, multi-market equity scanners, global opportunity ranking, watchlist builders.
2. **TAE JSON research pipeline** — strategy discovery, historical execution, candidate registry, continuous strategy ranking, hypothesis ranking.

**Neither stack feeds canonical `live_bot.py` ticker selection.** Live BUY uses only `watchlist.txt` + inline RSI/SMA scoring. TAE connects to live only as a **risk gate** via `tae_live_advisory.json` (can block BUY on `RISK_ADVISORY`; does not expand universe or trigger buys).

**Do not rebuild:** global ETF scanner, sector rotation, multi-market scanner, TAE ranking/registry/discovery engines, or historical execution batch runner. **Connect and govern** what exists.

---

## Answers to Audit Questions

### 1. What modules exist for global market observation?

See **EXISTING_MODULES** below. Summary by layer:

| Layer | Status | Primary paths |
|-------|--------|---------------|
| Global / regional ETF intelligence | Built, report-only | `strategic_intelligence/global_market_scanner.py`, `regional_strength_aggregator.py`, `strategic_bias_engine.py`, `capital_flow_*.py` |
| Sector rotation | Built, report-only | `sector_intelligence/sector_rotation_scanner.py` + history/momentum/flow analyzers |
| Equity market scanners | Built, manual/orphan live bridge | `research/market_scanner.py`, `multi_market_scanner.py`, `global_candidates.py`, `global_opportunity_ranking.py` |
| Universe builders | Built, research/manual | `research_core/universe.py`, `momentum_universe_expansion_v13.py`, `universe_from_candidates.py`, `auto_watchlist.py` |
| Daily gainers / momentum research | Built, analysis-only | `daily_gainers_strategy_research.py`, `daily_gainers_momentum_filter_research.py`, `momentum_continuation_engine.py` |
| TAE discovery / ranking / registry | Built, report/advisory | `research_core/discovery/`, `research_core/strategy_evolution/`, `research_core/strategy_simulation/` |
| Market session infrastructure | **Connected to live** | `markets/market_hours.py`, `markets/market_config.py` (per-ticker session gate only) |
| Event/psychology intelligence | **Blueprint only** | `TAE_MARKET_INTELLIGENCE_BLUEPRINT.md` (not implemented) |

### 2. What tickers / markets are covered?

| Module / artifact | Coverage |
|-------------------|----------|
| `global_market_scanner.py` | ETF proxies: SPY, QQQ, DIA, IWM, VGK, FEZ, EWU, EWJ, EWH, INDA (US, Europe, UK, Japan, HK, India) |
| `multi_market_scanner.py` | US (`watchlist_us.txt`), EU (`watchlist_eu.txt`), UK (`watchlist_uk.txt`); **ASIA disabled** in `markets/market_config.py` |
| `market_scanner.py` | ~500 S&P 500 names (Wikipedia scrape + fallback list) |
| `global_candidates.py` | Top 30 from multi-market scan → `watchlist_global.txt` |
| `us_expanded_universe.txt` | ~150+ US liquid names (research) |
| **Live `watchlist.txt`** | **15 tickers** (mix US + EU + UK: SPY, QQQ, NVDA, AAPL, MSFT, SIE.DE, MC.PA, HSBA.L, etc.) |
| TAE historical execution | US/EU/UK/ASIA per job config; max 5 tickers/market in backtest runner |
| TAE strategy ranking | **Strategy IDs**, not tickers — replayed from `portfolio.csv` evidence |

### 3. Connected to `live_bot.py` or report-only?

| Connection | Type |
|------------|------|
| `watchlist.txt` | **Direct live universe** — sole ticker source |
| `markets/market_hours.py` | **Live** — per-ticker BUY session filter |
| SPY SMA200 regime filter | **Live** — blocks STRONG BUY in BEAR |
| `live_advisory_runtime.py` → `tae_live_advisory.json` | **Live risk gate only** — blocks BUY on RISK_ADVISORY |
| All scanners, ranking, discovery, ETF intelligence | **Report-only** (or manual script) |
| `live_bot_v5_1.py` (orphan) | Auto-runs scanner chain → copies `watchlist_global.txt` → `watchlist.txt`; **not canonical** |

**Canonical `live_bot.py` imports zero scanner/ranking/discovery modules.**

### 4. Do they produce `tae_*.json` / CSV artifacts?

**Yes — both stacks produce artifacts; live bot reads almost none of them for ticker selection.**

See **ARTIFACTS_PRODUCED** and **ARTIFACTS_CONSUMED** below.

### 5. Does the dashboard display them?

| Shown in UI | Artifact / source |
|-------------|-------------------|
| **Yes** — Global Candidates tab | `global_candidates.csv` |
| **Yes** — Global Top Opportunities | `global_opportunity_ranking.csv` |
| **Yes** — Scanner Status | `watchlist_candidates.csv` |
| **Yes** — Adaptive Allocation | `adaptive_allocation.json` (backtest-derived regional strength, **not** live ETF scanner) |
| **Yes** — Pattern Discovery | `pattern_discovery_summary.txt` |
| **Yes** — TAE Intelligence Reports tab | All root `tae_*.json` (generic viewer) |
| **Yes** — TAE Command Center / Strategy Lab | `tae_full_ecosystem_review.json` → ranking shortlists, registry counts |
| **Yes** — Live strategy ranking expander | `tae_continuous_strategy_ranking.json` via ecosystem review |
| **No** | `global_market_scanner.csv`, `regional_strength.csv`, `sector_rotation.csv`, `multi_market_candidates.csv`, `watchlist_global.txt` |

### 6. Are they used for live BUY?

| Source | Used for live BUY? |
|--------|-------------------|
| `watchlist.txt` | **Yes** — only tickers scored and eligible |
| Inline score (RSI/SMA50, min 80) | **Yes** |
| Market session per ticker | **Yes** |
| `tae_live_advisory.json` | **Partial** — can **block** BUY; `BUY_ADVISORY` is log-only, no auto-buy |
| Global scanner / ranking / discovery | **No** |
| Dashboard scanner outputs | **No** (unless operator manually updates `watchlist.txt`) |

### 7. What is missing between these modules and live execution?

See **MISSING_LINKS** below. Core gap: **no governed adapter** from scanned/ranked candidates → `watchlist.txt` (or live config) in canonical `live_bot.py`.

### 8. Does a universe/ranking engine already exist?

**Yes — multiple, at different abstraction levels:**

| Engine | Granularity | Artifact |
|--------|-------------|----------|
| `research/global_candidates.py` + ranking | **Ticker-level** (top 30 global equities) | `global_candidates.csv`, `watchlist_global.txt` |
| `research_core/strategy_evolution/continuous_ranking_engine.py` | **Strategy-level** | `tae_continuous_strategy_ranking.json` |
| `research_core/strategy_evolution/candidate_registry.py` | **Strategy candidates** | `tae_candidate_strategy_registry.json` |
| `research_core/discovery/discovery_engine.py` | **Research hypotheses** | `tae_discoveries.json` |
| `edge_discovery_engine_v30.py` | **Edge rules** on US expanded universe | `edge_discovery_*.csv` |

**Reuse the ticker-level global pipeline and TAE strategy ranking for advisory context — do not build a third ranking engine.**

### 9. Difference between live `watchlist.txt` and global scanner/research?

| | **`watchlist.txt` (live)** | **Global scanner / research** |
|--|---------------------------|-------------------------------|
| Purpose | Canonical live trading universe | Candidate generation, backtests, advisory evidence |
| Size | ~15 tickers (current) | 30–500+ depending on pipeline stage |
| Update | Manual edit; optional scripts; orphan v5.1 auto-bridge | Batch scripts, research jobs |
| Consumer | `live_bot.py` reads every cycle | Dashboard, reports, TAE JSON pipeline |
| Markets | Curated mix US/EU/UK | US full S&P 500, regional watchlists, ETF macro layer |
| BUY impact | Direct | None unless operator copies output to `watchlist.txt` |

### 10. What can be reused immediately?

See **REUSABLE_NOW** and **DO_NOT_REBUILD** below.

---

## EXISTING_MODULES

### A. Global / regional macro intelligence (ETF-level)

| Module | Output | Mode |
|--------|--------|------|
| `strategic_intelligence/global_market_scanner.py` | `global_market_scanner.csv`, summary TXT | ANALYSIS_ONLY |
| `strategic_intelligence/regional_strength_aggregator.py` | `regional_strength.csv` | ANALYSIS_ONLY |
| `strategic_intelligence/strategic_bias_engine.py` | `strategic_bias.csv` | ANALYSIS_ONLY |
| `strategic_intelligence/capital_flow_*.py` | Flow summaries, `regional_strength_history.csv` | ANALYSIS_ONLY |
| `benchmark_intelligence/regional_benchmark_engine.py` | Benchmark vs regional strength | ANALYSIS_ONLY |
| `generate_adaptive_allocation.py` + `core/allocation_learning.py` | `adaptive_allocation.json` | PAPER_ONLY (parallel regional model) |

### B. Sector intelligence

| Module | Output | Mode |
|--------|--------|------|
| `sector_intelligence/sector_rotation_scanner.py` | `sector_rotation.csv` | ANALYSIS_ONLY |
| `sector_intelligence/sector_history_engine.py` | `sector_rotation_history.csv` | ANALYSIS_ONLY |
| `sector_intelligence/sector_momentum_analyzer.py` | Summary TXTs | ANALYSIS_ONLY |
| `sector_intelligence/sector_flow_analyzer.py` | Flow summaries | ANALYSIS_ONLY |
| `research/market_rotation.py` | `market_rotation.csv` from `global_candidates.csv` | ANALYSIS_ONLY |

### C. Equity scanners / universe builders

| Module | Output | Mode |
|--------|--------|------|
| `research/market_scanner.py` | `watchlist_candidates.csv`, optional `watchlist.txt` | Manual / orphan v5.1 |
| `research/multi_market_scanner.py` | `multi_market_candidates.csv` | Standalone script |
| `research/global_candidates.py` | `global_candidates.csv`, `watchlist_global.txt` | Standalone script |
| `research/global_opportunity_ranking.py` | `global_opportunity_ranking.csv` | Standalone script |
| `universe_from_candidates.py` | `watchlist.txt` from scanner CSV | Manual PAPER_ONLY |
| `auto_watchlist.py` | Top 20 US mega-caps → `watchlist.txt` | Manual |
| `research_core/universe.py` | Reads `us_expanded_universe.txt` | Research-only |
| `momentum_universe_expansion_v13.py` | `us_expanded_universe.txt` | RESEARCH_ONLY |
| `candidate_recovery_engine.py` | `candidate_recovery_watchlist.csv` | Report-only |
| `market_session_monitor.py` | Session history vs regional watchlists | Report-only |

### D. Daily gainers / momentum research

| Module | Output | Mode |
|--------|--------|------|
| `daily_gainers_strategy_research.py` | `daily_gainers_strategy_results.csv` | RESEARCH_ONLY |
| `daily_gainers_momentum_filter_research.py` | `daily_gainers_momentum_filter_results.csv` | RESEARCH_ONLY |
| `momentum_continuation_engine.py` | Uses daily gainers filter output | RESEARCH_ONLY |

### E. TAE discovery / ranking / historical execution

| Module | Output | Mode |
|--------|--------|------|
| `research_core/discovery/discovery_engine.py` | `tae_discoveries.json` | RESEARCH_ONLY |
| `research_core/strategy_discovery/` | `tae_strategy_discovery.json` | RESEARCH_ONLY |
| `tae_historical_execution_runner.py` | `tae_historical_execution.json` | RESEARCH_ONLY |
| `research_core/strategy_simulation/historical_results_analysis_report.py` | `tae_historical_results_analysis.json` | RESEARCH_ONLY |
| `research_core/strategy_evolution/candidate_registry.py` | `tae_candidate_strategy_registry.json` | ANALYSIS_ONLY |
| `research_core/strategy_evolution/continuous_ranking_engine.py` | `tae_continuous_strategy_ranking.json` | ANALYSIS_ONLY |
| `research_core/hypothesis/hypothesis_ranking.py` | `tae_hypothesis_rankings.json`, `tae_discovery_hypothesis_rankings.json` | RESEARCH_ONLY |
| `edge_discovery_engine_v30.py` | `edge_discovery_*.csv` | RESEARCH_ONLY |
| `pattern_discovery_engine.py` | `pattern_discovery_summary.txt` | Report-only |
| `research_core/services/market_data.py` | `MarketDataService` (OHLCV for backtests) | Research infrastructure |

### F. Live-connected (session / advisory only)

| Module | Role |
|--------|------|
| `markets/market_hours.py` | Per-ticker market open/closed — used by `live_bot.py` |
| `markets/market_config.py` | US/EU/UK enabled; ASIA disabled |
| `research_core/governance/live_advisory_bridge.py` | Builds `tae_live_advisory.json` from TAE reports + runtime |
| `research_core/governance/live_advisory_runtime.py` | Loaded by `live_bot.py` for BUY risk gate |

---

## REPORT_ONLY

Modules and artifacts that **observe/rank/scan but never drive canonical live execution**:

- Entire `strategic_intelligence/` ETF chain
- Entire `sector_intelligence/` chain
- `research/market_scanner.py`, `multi_market_scanner.py`, `global_opportunity_ranking.py` (unless manual watchlist update)
- All TAE discovery, historical execution, strategy ranking, candidate registry
- `daily_gainers_*` research scripts
- `edge_discovery_engine_v30.py`
- `pattern_discovery_engine.py` (dashboard display only)
- `TAE_MARKET_INTELLIGENCE_BLUEPRINT.md` (design doc, not code)

**Exception (orphan, not canonical):** `live_bot_v5_1.py` auto-runs scanner chain and overwrites `watchlist.txt` from `watchlist_global.txt`.

---

## CONNECTED_TO_LIVE

| Component | Connection | Effect on live |
|-----------|------------|----------------|
| `watchlist.txt` | Read every bot cycle | Defines scored universe |
| `markets/market_hours.py` | Per-ticker BUY gate | Blocks BUY when ticker's market closed |
| SPY SMA200 regime | `MARKET_REGIME_FILTER` | Blocks STRONG BUY in BEAR |
| `tae_live_advisory.json` | `should_block_new_buy()` in BUY path | Blocks new BUY on RISK_ADVISORY |
| `live_signals.csv` / `portfolio.csv` | Read/write each cycle | Signals and positions (not scanner input) |
| Shadow validation ledger | BUY path logging | Observability only |

**Not connected:** all scanner CSVs, ETF intelligence, sector rotation, TAE ranking JSON (except as advisory evidence), `watchlist_global.txt`.

---

## ARTIFACTS_PRODUCED

### CSV / TXT (legacy scanner chain)

| Artifact | Producer |
|----------|----------|
| `global_market_scanner.csv` | `global_market_scanner.py` |
| `regional_strength.csv` | `regional_strength_aggregator.py` |
| `strategic_bias.csv` | `strategic_bias_engine.py` |
| `sector_rotation.csv` | `sector_rotation_scanner.py` |
| `watchlist_candidates.csv` | `market_scanner.py`, `auto_watchlist.py` |
| `multi_market_candidates.csv` | `multi_market_scanner.py` |
| `global_candidates.csv` | `global_candidates.py` |
| `global_opportunity_ranking.csv` | `global_opportunity_ranking.py` |
| `watchlist_global.txt` | `global_candidates.py` |
| `adaptive_allocation.json` | `generate_adaptive_allocation.py` |
| `daily_gainers_strategy_results.csv` | daily gainers research |
| `edge_discovery_candidates.csv` | edge discovery v30 |
| `pattern_discovery_summary.txt` | `pattern_discovery_engine.py` |

### TAE JSON (research / advisory)

| Artifact | Role |
|----------|------|
| `tae_strategy_discovery.json` | Strategy hypothesis seeds |
| `tae_historical_execution.json` | Batch backtest results |
| `tae_historical_results_analysis.json` | Robust/weak strategy shortlists |
| `tae_candidate_strategy_registry.json` | Registered strategy candidates |
| `tae_continuous_strategy_ranking.json` | **Primary strategy ranking** |
| `tae_discoveries.json` | Phase IV discovery registry |
| `tae_hypothesis_rankings.json` | Hypothesis quality ranks |
| `tae_meta_intelligence.json` | Aggregated research conclusions |
| `tae_live_advisory.json` | **Only TAE artifact read by live bot** |
| `tae_full_ecosystem_review.json` | Daily consolidated review |
| `tae_advisory_index.json` | Index of available TAE reports |

---

## ARTIFACTS_CONSUMED

| Consumer | Reads |
|----------|-------|
| **`live_bot.py`** | `watchlist.txt`, `tae_live_advisory.json` (risk gate only) |
| **`live_advisory_bridge.py`** | `tae_advisory_index.json`, ranking/historical/meta JSON, `portfolio.csv`, `live_signals.csv` |
| **`dashboard_v2.py`** | `global_candidates.csv`, `global_opportunity_ranking.csv`, `watchlist_candidates.csv`, `adaptive_allocation.json`, all `tae_*.json`, pattern summary |
| **`dashboard_tae_command_center.py`** | `tae_full_ecosystem_review.json` (strategy universe, ranking top) |
| **`tae_full_ecosystem_review.py`** | Most TAE JSON + runtime CSVs |
| **`global_candidates.py`** | `multi_market_candidates.csv` |
| **`global_opportunity_ranking.py`** | `global_candidates.csv` + regional/rotation bonuses |
| **TAE ranking/registry engines** | Prior TAE JSON + `portfolio.csv` replay |

---

## REUSABLE_NOW

| Asset | Reuse path | Effort |
|-------|------------|--------|
| `research/multi_market_scanner.py` → `global_candidates.py` → `global_opportunity_ranking.csv` | Ticker-level global pipeline already ranks US/EU/UK equities | Wire to governed watchlist adapter (not rebuild) |
| `watchlist_global.txt` / top-30 from `global_candidates.csv` | Ready-made global shortlist | Manual or scripted merge into `watchlist.txt` today |
| `tae_continuous_strategy_ranking.json` | Advisory context + Strategy Lab | Already consumed by live advisory bridge |
| `tae_historical_results_analysis.json` | Robust/weak strategy evidence for BUY confidence | Already in advisory bridge |
| `markets/market_hours.py` + `market_config.py` | Per-market session enforcement | Already live |
| `live_advisory_bridge.py` + runtime staleness fix | Risk gate with runtime override | Already live |
| `dashboard_v2.py` scanner tabs | Operator visibility | Add panels for ETF/sector CSVs (UI only) |
| `research_core/services/market_data.py` | OHLCV for any future scheduled scan | Research infrastructure ready |
| `TAE_MARKET_INTELLIGENCE_BLUEPRINT.md` | Event/psychology layer design | Phase 2+ — not duplicate scanner work |

---

## MISSING_LINKS

| Gap | Impact |
|-----|--------|
| **No TAE → live universe bridge** | Ranking/discovery never updates `watchlist.txt` |
| **No scheduled scanner → live pipeline** | Canonical bot never auto-refreshes universe |
| **Two regional-strength models** | ETF scanner CSV vs `adaptive_allocation.json` — neither feeds live |
| **Sector rotation invisible** | `sector_rotation.csv` exists but no dashboard or live consumer |
| **ETF macro chain disconnected** | `global_market_scanner` → `regional_strength` → `strategic_bias` produces artifacts with no downstream wiring |
| **Advisory is risk-only** | `BUY_ADVISORY` does not expand universe or trigger buys |
| **Ranking is strategy-level** | `tae_continuous_strategy_ranking.json` ranks strategies, not scanner tickers |
| **ASIA disabled** | Config off; ETF scanner includes Asia proxies but equity multi-market path skips Asia |
| **Event intelligence not built** | Blueprint only (`TAE_MARKET_INTELLIGENCE_BLUEPRINT.md`) |
| **Governed adapter missing** | No `PAPER_ONLY` approval step: scan output → diff → `watchlist.txt` with audit trail |

---

## DO_NOT_REBUILD

| Capability | Existing owner | Reason |
|------------|----------------|--------|
| Global ETF market scanner | `strategic_intelligence/global_market_scanner.py` | Complete; needs wiring |
| Regional strength aggregation | `regional_strength_aggregator.py` | Complete |
| Sector rotation scanner | `sector_intelligence/sector_rotation_scanner.py` | Complete |
| S&P 500 / multi-market equity scanner | `research/market_scanner.py`, `multi_market_scanner.py` | Complete |
| Global candidate ranking | `global_candidates.py`, `global_opportunity_ranking.py` | Complete |
| US expanded research universe | `us_expanded_universe.txt`, `research_core/universe.py` | Complete |
| Strategy discovery pipeline | `research_core/strategy_discovery/` | Complete |
| Historical execution batch | `tae_historical_execution_runner.py` | Complete (1,475+ backtests) |
| Candidate registry | `candidate_registry.py` | Complete |
| Continuous strategy ranking | `continuous_ranking_engine.py` | Complete |
| Phase IV discovery | `discovery_engine.py` | Complete |
| Live advisory / risk gate | `live_advisory_bridge.py` | Complete (incl. staleness fix) |
| Per-ticker market session gate | `markets/market_hours.py` | Live and working |
| Dashboard TAE report viewer | `dashboard_v2.py` TAE tab | Complete |

**Build instead:** a thin **governance adapter** (read scan/rank outputs → propose watchlist diff → operator or scheduled approval → audit log). Not a new scanner or ranking engine.

---

## Architecture Snapshot

```
LEGACY CSV SCANNER CHAIN (report / manual)
  global_market_scanner → regional_strength → strategic_bias → capital_flow
  sector_rotation_scanner → sector history / momentum / flow
  market_scanner (S&P500) → watchlist_candidates.csv
  multi_market_scanner → global_candidates → global_opportunity_ranking
                              ↓
                        watchlist_global.txt ──(manual or v5.1 only)──→ watchlist.txt

TAE JSON RESEARCH PIPELINE (report / advisory)
  tae_strategy_discovery → tae_historical_execution → tae_historical_results_analysis
  tae_candidate_strategy_registry → tae_continuous_strategy_ranking
                              ↓
                        tae_live_advisory.json ──(risk gate only)──→ live_bot.py

LIVE SPINE (canonical)
  watchlist.txt → live_bot.py (RSI/SMA score) → live_signals.csv → manage_portfolio()
  markets/market_hours.py → per-ticker session filter
  tae_live_advisory.json → should_block_new_buy() on RISK_ADVISORY
```

---

## Validation

- **Code modified:** None (audit only)
- **New modules:** None
- **`live_bot.py` modified:** No
- **`watchlist.txt` modified:** No
- **Git status at audit time:** clean except unrelated `M tae_market_open_monitor.md`

---

## Final Recommendation

| Question | Answer |
|----------|--------|
| Does global market intelligence exist? | **PARTIAL — YES at research/report layer, NO at live execution layer** |
| What to connect (not rebuild)? | (1) Global equity pipeline → governed `watchlist.txt` adapter, (2) ETF/sector CSVs → dashboard panels + optional advisory context, (3) existing TAE ranking → already in advisory; extend only if ticker-level ranking needed |
| Immediate operator path | Run `multi_market_scanner` → `global_candidates` → review `global_opportunity_ranking.csv` in dashboard → manually merge top names into `watchlist.txt` |
| Next engineering step | **Watchlist governance adapter** with audit trail — not a new scanner |
