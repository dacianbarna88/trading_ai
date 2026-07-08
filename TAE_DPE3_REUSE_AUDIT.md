# TAE DPE-3 Pre-Build Audit — Paper Executor Reuse Audit

**Sprint:** DPE-3 Pre-Build Audit (Phase 0 — Ecosystem Audit)  
**Date:** 2026-07-07  
**Authority:** `TAE_MASTER_DEVELOPMENT_WORKFLOW.md` — Audit → Architecture → Reuse → Build  
**Mode:** READ_ONLY · NO_BROKER · NO_EXECUTION · NO_PORTFOLIO_CHANGE · NO_LIVE_BOT_CHANGE · NO_ADVISORY_CHANGE · NO_COMMIT  
**Status:** **PASS**

---

## Executive summary

TAE does **not** contain a ready-made **Competitive Paper Executor** or isolated virtual portfolio store for DPE. Live BUY/SELL exists only in `live_bot.py` (with parallel logic in `core/trades.py`). DPE-1 and DPE-2 are operational and produce `READY` COMPETITIVE jobs in `runtime_outputs/dpe/execution_jobs.jsonl`.

Several **partially reusable primitives** exist: trade helpers, FIFO accounting, CSV I/O patterns, shadow action vocabulary, and job routing schema. Historical backtest engines, counterfactual analyzers, and strategy-evolution “paper validators” are **not** forward paper executors and must not be mistaken for DPE-3.

**Estimated reuse:** ~45–55% of DPE-3 logic can compose existing modules.  
**Estimated new code:** ~45–55% (DPE job consumer, isolated store, fill journal, competitive philosophy mapping).

**Final verdict:** **READY_FOR_DPE3**

---

## Repository searched

| Scope | Files inspected |
|-------|-----------------|
| `research_core/` | 354 Python modules (full tree grep + targeted reads) |
| `core/` | `trades.py`, `portfolio.py`, `portfolio_prices.py`, `v41_shadow.py`, `market_data_layer.py` |
| `engine/` | Empty (`__init__.py` only) |
| `markets/` | `market_hours.py`, `market_config.py` |
| `runtime_outputs/` | `dpe/decision_events.jsonl`, `dpe/execution_jobs.jsonl` (no `paper_competitive/` yet) |
| Root-level Python | ~267 modules (filename + symbol grep) |

**Search terms used:** paper, virtual, simulation, executor, execution, portfolio, portfolio_manager, position, trade, buy, sell, order, broker, replay, counterfactual, shadow, journal, ledger, backtest

**Architecture references read:** `TAE_DUAL_PHILOSOPHY_EXECUTION_ARCHITECTURE.md`, `tae_dual_execution_architecture.json`, `TAE_DPE2_EXECUTION_SPLITTER_REPORT.md`

---

## Capability evaluation (10 required)

| # | Capability | Verdict | Evidence |
|---|------------|---------|----------|
| 1 | Paper BUY execution | **PARTIAL** | `core/trades.buy_position` + duplicated `live_bot.buy_position`; no isolated paper path |
| 2 | Paper SELL execution | **PARTIAL** | `core/trades.sell_position` + FIFO in `live_bot.py` / `execution_integrity.py`; no paper consumer |
| 3 | Virtual portfolio storage | **NO** | Only live `portfolio.csv`; architecture specifies `runtime_outputs/dpe/paper_competitive/` — **not created** |
| 4 | Position lifecycle | **PARTIAL** | FIFO/lot logic scattered across live_bot, simulation_lab, counterfactual modules |
| 5 | Trade history | **PARTIAL** | Live history = `portfolio.csv`; DPE jobs are intent records, not fills |
| 6 | Order journal | **PARTIAL** | `shadow_validation_ledger`, DPE JSONL logs (intent); no fill/execution journal |
| 7 | Replay execution | **NO** | `tae_decision_replay_composer.py` / `decision_replay_engine.py` analyze outcomes only |
| 8 | Counterfactual execution | **PARTIAL** | Historical what-if (`counterfactual_entry.py`, `counterfactual_exit.py`, shadow attribution) — not forward paper |
| 9 | Execution abstraction | **NO** | No shared `Executor` interface; `HistoricalExecutionEngine` is backtest-only |
| 10 | Shared execution utilities | **PARTIAL** | `core/trades`, `core/portfolio`, `data/storage`, `execution_integrity` — fragmented; live_bot bypasses `core/trades` |

---

## Modules inspected (candidate inventory)

### Live / production execution

#### `live_bot.py`
- **Purpose:** Production trading loop — gates BUYs, executes BUY/SELL, writes `portfolio.csv`, Telegram alerts.
- **Maturity:** Production
- **Dependencies:** pandas, yfinance, `markets.market_hours`, `core.market_data_layer`, `research_core.governance.shadow_validation_ledger`
- **Live impact:** **YES** — sole live trade writer
- **Reusable for DPE-3:** Partial (~25%) — reference for row schema and FIFO sell; **must not be called or modified**
- **Reuse %:** 25%

#### `core/trades.py`
- **Purpose:** Canonical BUY/SELL helpers — cash reserve, realized PnL, accounting annotations, Telegram.
- **Maturity:** Production (live_bot duplicates inline instead of importing)
- **Dependencies:** pandas, `core.portfolio`, `config.settings`, `utils.logger`, `utils.telegram`
- **Live impact:** Indirect — intended shared layer
- **Reusable for DPE-3:** **Yes (~70%)** — adapt for parameterized paper portfolio path
- **Reuse %:** 70%

#### `core/portfolio.py`
- **Purpose:** `get_open_positions`, `get_cash_available` from CSV rows.
- **Maturity:** Production
- **Dependencies:** pandas, `config.settings`
- **Live impact:** **YES**
- **Reusable for DPE-3:** Partial (~50%)
- **Reuse %:** 50%

#### `data/storage.py`
- **Purpose:** `load_portfolio` / `save_portfolio` for `portfolio.csv`.
- **Maturity:** Production
- **Dependencies:** pandas, `config.settings`
- **Live impact:** **YES**
- **Reusable for DPE-3:** Partial (~60%) — pattern with alternate path constant
- **Reuse %:** 60%

#### `core/portfolio_prices.py`
- **Purpose:** Mark-to-market open BUY rows; respects immutable rows.
- **Maturity:** Production
- **Dependencies:** `core.trades`, `data.storage`
- **Live impact:** **YES** (display fields on live portfolio)
- **Reusable for DPE-3:** Partial (~55%) — MTM for paper portfolio
- **Reuse %:** 55%

---

### DPE pipeline (upstream — mandatory input)

#### `tae_decision_event_bus.py`
- **Purpose:** DPE-1 — immutable decision snapshots → `decision_events.jsonl`.
- **Maturity:** Shadow (operational)
- **Dependencies:** JSON/CSV artifacts only (stdlib)
- **Live impact:** **NO**
- **Reusable for DPE-3:** Partial (~30%) — snapshot schema, audit lineage
- **Reuse %:** 30%

#### `tae_execution_splitter.py`
- **Purpose:** DPE-2 — fans events into COMPETITIVE + COLLABORATIVE jobs.
- **Maturity:** Shadow (operational)
- **Dependencies:** `decision_events.jsonl`, GII, APPE, PPG, targets, philosophy JSON
- **Live impact:** **NO**
- **Reusable for DPE-3:** **Yes (~85%)** — primary input contract
- **Reuse %:** 85%

#### `runtime_outputs/dpe/execution_jobs.jsonl`
- **Purpose:** Append-only job queue (`action_candidate`, snapshots, status READY/BLOCKED).
- **Maturity:** Shadow (data artifact)
- **Live impact:** **NO**
- **Reusable for DPE-3:** **Yes (100%)** — mandatory input

---

### Accounting / position integrity (read-only patterns)

#### `research_core/accounting/execution_integrity.py`
- **Purpose:** FIFO average-cost SELL reconciliation against `portfolio.csv`.
- **Maturity:** Production-quality audit
- **Dependencies:** stdlib csv
- **Live impact:** **NO** (reads live portfolio)
- **Reusable for DPE-3:** **Yes (~75%)** — FIFO lot model, PnL validation
- **Reuse %:** 75%

#### `research_core/accounting/accounting_snapshot.py`
- **Purpose:** Read-only accounting SSOT from portfolio + execution integrity.
- **Maturity:** Production-quality shadow/canonical
- **Dependencies:** `execution_integrity`, `capital_base_integrity`
- **Live impact:** **NO**
- **Reusable for DPE-3:** Partial (~50%) — pattern for `tae_dpe_accounting_competitive.json`
- **Reuse %:** 50%

---

### Shadow / hypothetical (not forward paper execution)

#### `tae_profit_protection_shadow.py`
- **Purpose:** Hypothetical profit-protection strategies vs live portfolio (read-only).
- **Maturity:** Shadow
- **Dependencies:** FIFO from fade intelligence, `portfolio.csv` read
- **Live impact:** **NO**
- **Reusable for DPE-3:** Partial (~45%) — action vocabulary (partial TP, trail, protect)
- **Reuse %:** 45%

#### `research_core/governance/shadow_validation_ledger.py`
- **Purpose:** Append-only BUY evaluation events from live_bot (observability).
- **Maturity:** Shadow (connected to live_bot writer)
- **Live impact:** **NO** (never blocks live)
- **Reusable for DPE-3:** Partial (~20%) — journal pattern only
- **Reuse %:** 20%

#### `research_core/governance/shadow_outcome_attribution.py`
- **Purpose:** Counterfactual outcomes for blocked BUYs using historical prices.
- **Maturity:** Shadow
- **Live impact:** **NO**
- **Reusable for DPE-3:** Partial (~25%) — counterfactual methodology, not execution
- **Reuse %:** 25%

#### `core/v41_shadow.py`
- **Purpose:** Logs V4 vs V41 strategy disagreements — no execution.
- **Maturity:** Shadow
- **Reusable for DPE-3:** No (~5%)
- **Reuse %:** 5%

---

### Simulation / counterfactual / backtest (historical — wrong domain)

#### `research_core/entry_analysis/counterfactual_entry.py`
- **Purpose:** Replays historical BUY rows with alternative filters on `portfolio.csv`.
- **Maturity:** Prototype/research
- **Reusable for DPE-3:** Partial (~35%) — lot tracking; historical not forward
- **Reuse %:** 35%

#### `research_core/exit_analysis/counterfactual_exit.py`
- **Purpose:** Simulates alternative exit horizons for closed SELLs.
- **Maturity:** Prototype/research
- **Reusable for DPE-3:** Partial (~30%)
- **Reuse %:** 30%

#### `research_core/simulation_lab/strategy_simulation_lab.py`
- **Purpose:** Compares baseline vs filtered entry strategies on historical BUYs.
- **Maturity:** Shadow/research
- **Reusable for DPE-3:** Partial (~40%) — FIFO `_BuyLot` dataclass patterns
- **Reuse %:** 40%

#### `research_core/strategy_simulation/historical_execution_engine.py`
- **Purpose:** Batch runner for **historical backtest jobs** — explicitly `NO_PORTFOLIO_CHANGE`.
- **Maturity:** Research pipeline (name collision risk with DPE “executor”)
- **Reusable for DPE-3:** **No (~10%)** — checkpoint/job pattern only
- **Reuse %:** 10%

#### `research_core/strategy_simulation/historical_backtest_runner.py`
- **Purpose:** OHLCV backtest engine for discovery strategies.
- **Maturity:** Research
- **Reusable for DPE-3:** No (~5%)
- **Reuse %:** 5%

#### `research_core/strategy_evolution/parallel_paper_validator.py`
- **Purpose:** Validates candidate strategies vs baseline — **no trades executed**.
- **Maturity:** Shadow pipeline step
- **Reusable for DPE-3:** **No (~10%)** — promotion analytics, not execution
- **Reuse %:** 10%

#### `research_core/strategy_evolution/paper_tracking_log.py`
- **Purpose:** Tracks paper-trade counts for promotion eligibility — reads metrics only.
- **Maturity:** Shadow pipeline step
- **Reusable for DPE-3:** No (~5%)
- **Reuse %:** 5%

---

### Replay / misc / stubs

#### `tae_decision_replay_composer.py`
- **Purpose:** Consolidates performance SSOT into replay VIEW; forbids BUY/SELL.
- **Maturity:** Shadow
- **Reusable for DPE-3:** No (~5%)
- **Reuse %:** 5%

#### `decision_replay_engine.py`
- **Purpose:** Win-rate stats from `decision_registry.csv`.
- **Maturity:** Prototype script
- **Reusable for DPE-3:** No
- **Reuse %:** 0%

#### `research/apply_rebalance_paper.py`
- **Purpose:** Appends simulated SELL rows to **live** `portfolio.csv` for REDUCE recommendations.
- **Maturity:** Prototype (**anti-pattern for DPE** — writes live store)
- **Reusable for DPE-3:** **No** — must never be used for DPE paths
- **Reuse %:** 0%

#### `research/rebalance_execution_simulator.py`
- **Purpose:** Print-only rebalance simulation.
- **Maturity:** Stub/script
- **Reusable for DPE-3:** No
- **Reuse %:** 0%

#### `threshold_virtual_tracker.py`
- **Purpose:** Compares score-threshold candidate sets; writes virtual candidate CSV.
- **Maturity:** Prototype
- **Reusable for DPE-3:** No
- **Reuse %:** 0%

#### `paper_trading_decision.py`
- **Purpose:** **Stub** — single comment line (`# generated by V9.0.0`).
- **Maturity:** Stub (empty)
- **Reusable for DPE-3:** No
- **Reuse %:** 0%

#### `tae_opportunity_cost_ledger.py`
- **Purpose:** Classifies missed-profit reasons — read-only ledger.
- **Maturity:** Shadow
- **Reusable for DPE-3:** Partial (~30%) — post-execution metrics concept
- **Reuse %:** 30%

---

### Markets

#### `markets/market_hours.py`, `markets/market_config.py`
- **Purpose:** Session gating, ticker→market resolution.
- **Maturity:** Production
- **Live impact:** **YES** (live_bot session checks)
- **Reusable for DPE-3:** Partial (~40%) — session-aware paper execution
- **Reuse %:** 40%

---

## Reusable modules (ranked for DPE-3)

| Rank | Module | Role in DPE-3 |
|------|--------|---------------|
| 1 | `runtime_outputs/dpe/execution_jobs.jsonl` | Input queue |
| 2 | `tae_execution_splitter.py` (job schema) | Contract definition |
| 3 | `core/trades.py` | BUY/SELL row creation, PnL |
| 4 | `research_core/accounting/execution_integrity.py` | FIFO validation |
| 5 | `data/storage.py` | CSV I/O pattern |
| 6 | `core/portfolio.py` | Cash/position math |
| 7 | `core/portfolio_prices.py` | Mark-to-market |
| 8 | `tae_profit_protection_shadow.py` | Action vocabulary reference |
| 9 | `research_core/accounting/accounting_snapshot.py` | Paper accounting JSON pattern |
| 10 | `markets/market_hours.py` | Session gating |

---

## Duplication audit

**If DPE-3 is implemented today without composing existing layers, these files would duplicate functionality:**

| File | Duplicated concern |
|------|-------------------|
| `live_bot.py` | BUY/SELL row creation, sizing, FIFO sell, portfolio I/O |
| `core/trades.py` | Trade helpers (already extracted; would be reimplemented) |
| `core/portfolio.py` | Cash and open-position math |
| `data/storage.py` | CSV load/save |
| `research_core/accounting/execution_integrity.py` | FIFO reconciliation and PnL |
| `research_core/accounting/accounting_snapshot.py` | Paper accounting derivation |
| `core/portfolio_prices.py` | Mark-to-market updates |
| `tae_execution_splitter.py` | Job parsing/routing (DPE-3 must consume, not rebuild) |
| `tae_decision_event_bus.py` | Snapshot normalization |
| `research_core/simulation_lab/strategy_simulation_lab.py` | FIFO lot dataclasses |
| `research_core/entry_analysis/counterfactual_entry.py` | Lot tracking / scenario sizing |
| `research_core/exit_analysis/counterfactual_exit.py` | Exit PnL simulation |
| `tae_profit_protection_shadow.py` | Shadow action → trade intent mapping |
| `research/apply_rebalance_paper.py` | Paper SELL append (wrong target — live CSV) |
| `research_core/strategy_simulation/historical_execution_engine.py` | Job batch/checkpoint naming collision |

**Misleading names (do not reuse as DPE executors):**

- `HistoricalExecutionEngine` — historical backtest batch runner
- `ParallelPaperValidator` — strategy promotion validator, no fills
- `paper_trading_decision.py` — empty stub
- `apply_rebalance_paper.py` — writes live portfolio

---

## Architecture gap vs target state

Per `tae_dual_execution_architecture.json`:

| Requirement | Current state |
|-------------|---------------|
| Consume `COMPETITIVE` + `READY` jobs | Input exists (78 jobs in log) |
| Write `runtime_outputs/dpe/paper_competitive/portfolio.csv` | **Not created** |
| Write `paper_competitive/trades.jsonl` | **Not created** |
| Never touch live `portfolio.csv` | No DPE executor yet — safe |
| Map `action_candidate` → paper fills | **Unimplemented** |
| `engine/` module home | **Empty** |

---

## Estimated effort split

| Category | Estimate |
|----------|----------|
| **Reuse (compose existing)** | **45–55%** |
| **New code (DPE-specific)** | **45–55%** |

**New code primarily covers:** job consumer loop, competitive philosophy action mapping, isolated store bootstrap, fill journal, idempotent job processing, DPE safety guards, CLI/reporting.

---

## Duplication risks

1. **Reimplementing FIFO/PnL** instead of importing `execution_integrity` / `core/trades` patterns.
2. **Naming collision** with `HistoricalExecutionEngine` — DPE module must use `dpe_competitive_executor` naming.
3. **Accidental live portfolio writes** — `apply_rebalance_paper.py` and `data/storage.PORTFOLIO_FILE` default path.
4. **Confusing strategy-evolution “paper” modules** with DPE paper execution.
5. **Rebuilding job schema** instead of reading DPE-2 output.
6. **live_bot duplication drift** — DPE-3 should use `core/trades`, not copy from `live_bot.py`.

---

## Recommended architecture

See **`TAE_DPE3_RECOMMENDATION.md`** — **OPTION C: Build new isolated executor** with composition of existing utilities.

---

## Validation

| Check | Result |
|-------|--------|
| Repository searched | ✅ |
| Priority paths inspected | ✅ |
| 10 capabilities evaluated | ✅ |
| Duplication audit complete | ✅ |
| Architecture recommendation documented | ✅ |
| No code written | ✅ |
| No files modified (except audit deliverables) | ✅ |
| No commit | ✅ |

---

## Roadmap position

```text
✅ DPE-1 Decision Event Bus
✅ DPE-2 Execution Splitter
✅ DPE-3 Pre-Build Audit          ← THIS SPRINT
→  DPE-3 Competitive Paper Executor ← NEXT (after audit gate)
   DPE-4 Collaborative Paper Executor
   DPE-5 Daily Result Evaluator
```

---

## Safety confirmation

| Rule | Status |
|------|--------|
| READ_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_EXECUTION | ✅ |
| NO_PORTFOLIO_CHANGE | ✅ |
| NO_LIVE_BOT_CHANGE | ✅ |
| NO_ADVISORY_CHANGE | ✅ |
| NO_COMMIT | ✅ |

---

## Overall verdict

**PASS**

**Final verdict:** **READY_FOR_DPE3**

The ecosystem audit is complete. No existing module satisfies DPE-3 as-is, but sufficient reusable primitives exist to avoid building a second live-style execution engine. Proceed to DPE-3 build using **OPTION C** (new isolated executor composing `core/trades`, `execution_integrity`, and DPE-2 job schema).

**Recommended next sprint:** TAE DPE-3 — Competitive Paper Executor

---

## Related deliverables

- Module matrix: `TAE_DPE3_REUSE_MATRIX.md`
- Architecture choice: `TAE_DPE3_RECOMMENDATION.md`
