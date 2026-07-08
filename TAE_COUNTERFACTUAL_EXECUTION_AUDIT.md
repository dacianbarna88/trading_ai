# TAE Counterfactual / Liquidation / PAPER Execution Audit

**Generated:** 2026-07-07T16:15:00+00:00  
**Mode:** READ_ONLY audit — no code changes, no live mutation  
**Branch context:** post `5b4d06c` (PAPER execution enabled)

---

## 1. Executive Verdict

### **EXISTING_MODULES_NEED_WIRING**

TAE already has substantial counterfactual, validation, and PAPER execution infrastructure — but **none of the five operator questions are fully answerable from a single integrated path today**.

| Question | Status today |
|---|---|
| 1. Sell all current positions now? | **CAPABILITY_MISSING** — no sell-all / liquidation scenario module |
| 2. Execute all PROMISING PAPER decisions? | **PARTIAL** — validation scores PROMISING; execution does not filter on verdict |
| 3. What if TAE had executed SELL/BUY/PROTECT/ROTATE? | **PARTIAL** — `tae_paper_execution.py` simulates actions; not replayed against historical canonical state |
| 4. Canonical vs full PAPER executed portfolio? | **PARTIAL** — both states exist as JSON; no dedicated comparator module |
| 5. Which rules improved/worsened performance? | **PARTIAL** — rule attribution exists; not tied to canonical PnL delta |

**Bottom line:** Do **not** build a new engine yet. Wire and extend existing modules first.

---

## 2. Execution Boundary (live_bot.py)

| Check | Finding |
|---|---|
| Broker connected? | **No** — no broker SDK; yfinance + Telegram + local CSV only |
| Real orders? | **No** — appends BUY/SELL rows to `portfolio.csv` |
| Classification | **LOCAL_PAPER_RUNTIME** — local journal, not broker-connected |
| Canonical live SSOT | `portfolio.csv`, `live_signals.csv` |
| Isolated PAPER SSOT | `runtime_outputs/paper_execution/paper_portfolio.json` |
| DPE isolated SSOT | `runtime_outputs/dpe/paper_competitive/`, `paper_collaborative/` |

`live_bot.py` remains protected. PAPER execution writes only under `runtime_outputs/paper_execution/`.

---

## 3. Candidate Module Matrix

| Module | Purpose | Inputs | Outputs | A sell-all | B PROMISING exec | C canonical vs paper | D rule attr | E action sim | Integration | CLI | In full-paper-cycle | Safety | Mutates |
|---|---|---|---|:---:|:---:|:---:|:---:|:---:|---|---|---|---|---|
| `tae_paper_execution.py` | Apply PDE decisions to isolated PAPER portfolio | `paper_decisions.json`, `tae_accounting_snapshot.json` | `paper_portfolio.json`, `paper_orders.jsonl`, `paper_trades.jsonl`, `rule_outcome_attribution.json` | ❌ | ❌ | ❌ | ✅ | ✅ | **FULLY_INTEGRATED** | `paper-execution` | ✅ step 6 | PAPER_ONLY | `runtime_outputs/paper_execution/` |
| `tae_dpe_paper_executor_infra.py` | Shared DPE executor + PDE validation scoring | `execution_jobs.jsonl`, `paper_decisions.json` | DPE portfolios, `decision_validation_results.json` | ❌ | ⚠️ scores | ❌ | ⚠️ | ⚠️ trim/protect | **FULLY_INTEGRATED** | — | ✅ via experiments + DPE | PAPER_ONLY | `runtime_outputs/` |
| `tae_dpe_competitive_executor.py` | Competitive philosophy paper fills | `execution_jobs.jsonl` | `dpe/paper_competitive/*` | ❌ | ❌ | ❌ | ❌ | ⚠️ | **FULLY_INTEGRATED** | `dpe-competitive` | ✅ | SHADOW_ONLY | DPE dir only |
| `tae_dpe_collaborative_executor.py` | Collaborative philosophy paper fills | `execution_jobs.jsonl` | `dpe/paper_collaborative/*` | ❌ | ❌ | ❌ | ❌ | ⚠️ | **FULLY_INTEGRATED** | `dpe-collaborative` | ✅ | SHADOW_ONLY | DPE dir only |
| `tae_paper_decision_engine.py` | Emit PAPER decisions (no execution) | GII, accounting, knowledge, weights, etc. | `paper_decisions.json` | ❌ | ⚠️ scoring | ❌ | ✅ | ⚠️ emits | **FULLY_INTEGRATED** | `paper-decisions` | ✅ | READ_ONLY | `runtime_outputs/paper_decisions/` |
| `tae_paper_experiment_runner.py` | Hypothesis scoring + triggers validation | LTP queue, experiments | `experiment_results.json`, validation | ❌ | ✅ verdicts | ⚠️ DPE compare | ⚠️ | ❌ | **FULLY_INTEGRATED** | `paper-experiments` | ✅ | READ_ONLY | `runtime_outputs/learning_to_profit/` |
| `tae_adaptive_paper_weights.py` | Evidence-driven action weights | validation, attribution, hints | `paper_action_weights.json` | ❌ | ❌ | ❌ | ⚠️ consumes | ❌ | **FULLY_INTEGRATED** | `adaptive-weights` | ✅ (pre-decisions) | PAPER_ONLY | `runtime_outputs/adaptive_weights/` |
| `tae_longitudinal_outcome_memory.py` | Canonical PAPER decision lifecycle | decisions, validation, experiments | `decisions.jsonl`, hints, knowledge | ❌ | ❌ | ❌ | ⚠️ | ❌ | **FULLY_INTEGRATED** | `outcome-memory` | ✅ | PAPER_ONLY | `runtime_outputs/longitudinal_memory/` |
| `tae_dpe_result_evaluator.py` | Compare competitive vs collaborative paper | DPE portfolio JSONs | `evaluation.json` | ❌ | ❌ | ⚠️ DPE only | ❌ | ❌ | **FULLY_INTEGRATED** | `dpe-evaluator` | ✅ | READ_ONLY | `runtime_outputs/dpe/result_evaluator/` |
| `tae_profit_protection_validation.py` | Historical shadow protection vs HOLD | fade history, shadow JSON | `tae_profit_protection_validation.json` | ❌ | ❌ | ⚠️ vs HOLD | ⚠️ strategy | ⚠️ shadow | **PARTIALLY_CONNECTED** | — | upstream intel | SHADOW_ONLY | reports only |
| `tae_decision_replay_composer.py` | Shadow replay consolidation | accounting, protect, cooldown, registry | `tae_decision_replay.json` | ❌ | ❌ | ⚠️ protect/cooldown CF | ⚠️ | ❌ | **PARTIALLY_CONNECTED** | — | consumed by PDE | SHADOW_ONLY | `tae_decision_replay.*` |
| `tae_opportunity_cost_ledger.py` | Missed-profit diagnostic | GII, shadow, accounting | `tae_opportunity_cost_ledger.json` | ❌ | ❌ | ❌ | ❌ | ❌ | **PARTIALLY_CONNECTED** | `opportunity` | summary read | SHADOW_ONLY | reports only |
| `tae_profit_growth_analytics.py` | Growth analytics SSOT join | accounting, governors | `tae_profit_growth_analytics.json` | ❌ | ❌ | ❌ | ❌ | ❌ | **PARTIALLY_CONNECTED** | `growth-analytics` | upstream | READ_ONLY | reports only |
| `tae_winner_lifecycle_profiler.py` | Winner lifecycle stages | analytics, ledger | `tae_winner_lifecycle_profiler.json` | ❌ | ❌ | ❌ | ❌ | ❌ | **PARTIALLY_CONNECTED** | `winner` | upstream | READ_ONLY | reports only |
| `research_core/exit_analysis/counterfactual_exit.py` | Alt exit timing on closed SELLs | `portfolio.csv` (read) | exit counterfactual report | ❌ | ❌ | ⚠️ exit timing | ❌ | ❌ | **EXISTS_NOT_CONNECTED** | demo only | ❌ | ANALYSIS_ONLY | none |
| `research_core/entry_analysis/counterfactual_entry.py` | Alt entry filters/sizing | `portfolio.csv` (read) | entry counterfactual report | ❌ | ❌ | ⚠️ entry CF | ❌ | ❌ | **EXISTS_NOT_CONNECTED** | demo only | ❌ | ANALYSIS_ONLY | none |
| `tae_counterfactual_runtime.py` | Legacy CF orchestrator | demo scripts | `tae_counterfactual_runtime.json` | ❌ | ❌ | ❌ | ❌ | ❌ | **LEGACY** | — | ❌ | LEGACY | reports only |
| `research_core/strategy_evolution/parallel_paper_validator.py` | Candidate vs LIVE_BASELINE | registry, `portfolio.csv` | parallel validation report | ❌ | ❌ | ✅ candidates | ❌ | ❌ | **EXISTS_NOT_CONNECTED** | demo/pipeline | ❌ | ANALYSIS_ONLY | none |
| `research_core/simulation_lab/strategy_simulation_lab.py` | Baseline BUY vs alt filters | `portfolio.csv` | simulation lab report | ❌ | ❌ | ⚠️ entry baseline | ❌ | ❌ | **EXISTS_NOT_CONNECTED** | — | ❌ | ANALYSIS_ONLY | none |
| `decision_replay_engine.py` | Legacy registry win-rate replay | `decision_registry.csv` | `decision_replay_summary.txt` | ❌ | ❌ | ❌ | ❌ | ❌ | **LEGACY** | — | ❌ | ANALYSIS_ONLY | registry |
| `outcome_evaluator.py` | Registry outcome updates | `decision_registry.csv` | summary txt | ❌ | ❌ | ❌ | ❌ | ❌ | **LEGACY** | — | ❌ | ANALYSIS_ONLY | **decision_registry.csv** |
| `live_bot.py` | Local CSV trading loop | watchlist, yfinance | `portfolio.csv` | ❌ | ❌ | canonical source | ❌ | ✅ local | **LIVE_RISK** (local) | direct script | ❌ forbidden | LOCAL_PAPER_RUNTIME | **`portfolio.csv`** |

**Grep result:** Zero matches for `sell all`, `liquidate`, `close all`, `liquidation`, `exit all` in `*.py`.

---

## 4. Existing Capability Map

### Sell-all now
- **Status:** **MISSING**
- **Nearest:** per-ticker `SELL_PAPER` in `tae_paper_execution.py`; per-position `sell_position()` in `live_bot.py`
- **Data available:** `tae_accounting_snapshot.json` has 12 open positions, `$28,005.63` open value, `$2,335.28` cash → liquidation would be ~$30,340.91 all-cash (minus spread assumptions)

### Execute all PROMISING decisions
- **Status:** **PARTIAL**
- **Scoring:** `run_paper_decision_validation()` in `tae_dpe_paper_executor_infra.py` — current run: **3 PROMISING** (AMAT PROTECT_PAPER, MU PROTECT_PAPER, HSBA.L SELL_PAPER)
- **Execution:** `tae_paper_execution.py` executes **all** unprocessed PDE decisions (25 orders last run), **not** PROMISING-filtered
- **Cycle gap:** `paper-execution` runs **before** `paper-experiments` (which produces validation verdicts)

### Canonical vs PAPER comparison
- **Status:** **PARTIAL — data exists, no comparator**
- **Canonical (read-only):** `tae_accounting_snapshot.json` → $30,340.91 total, $2,335.28 cash, **12 positions**
- **PAPER executed:** `runtime_outputs/paper_execution/paper_portfolio.json` → $30,340.92 total, $5,390.69 cash, **11 positions**
- **Observed delta:** 3 SELL_PAPER fills closed HSBA.L (+$3,055 cash shift); canonical unchanged
- **No module** diffs these side-by-side or computes counterfactual PnL uplift

### Rule attribution
- **Status:** **PARTIAL — exists, not tied to canonical PnL**
- **Primary:** `runtime_outputs/paper_execution/rule_outcome_attribution.json` — **24 rules** tracked
- **PDE source:** `hypothesis_rules_applied`, `knowledge_evidence` per decision
- **Feedback:** `tae_adaptive_paper_weights.py` reads attribution for capped weight deltas
- **Gap:** attribution uses simulated/expected deltas, not measured canonical portfolio improvement

### Buy/sell/protect/rotate simulation
- **Status:** **PARTIAL — two parallel tracks**
- **PDE track (full actions):** `tae_paper_execution.py` — BUY/SELL/PROTECT/REDUCE/ROTATE/HOLD/SKIP
- **DPE track (subset):** competitive/collaborative executors — HOLD/TRIM/PROTECT/SKIP only
- **Historical CF:** exit/entry counterfactual modules (research_core) — timing/filter what-if on past trades
- **Shadow:** `tae_profit_protection_validation.py` — historical shadow trim/trail vs HOLD

---

## 5. Specific Question Answers

| # | Question | Answer |
|---|---|---|
| 1 | Sell-all / liquidation analyzer? | **No.** Closest is per-ticker SELL_PAPER. Liquidation value derivable from accounting snapshot but no scenario runner. |
| 2 | Paper execution engine for simulated portfolio? | **Yes.** `tae_paper_execution.py` — integrated in `full-paper-cycle`. |
| 3 | Canonical-vs-paper comparator? | **No dedicated module.** Data in `tae_accounting_snapshot.json` vs `paper_portfolio.json`. DPE evaluator compares competitive vs collaborative only. |
| 4 | Counterfactual exit/protect/hold simulator? | **Yes, fragmented.** `tae_profit_protection_validation.py` (shadow vs HOLD), `tae_decision_replay_composer.py` (protect/cooldown CF), `research_core/exit_analysis/counterfactual_exit.py` (exit timing). Not wired to PAPER execution portfolio. |
| 5 | Rule outcome attribution? | **Yes.** `rule_outcome_attribution.json` + adaptive weights consumption. Not connected to canonical PnL proof. |
| 6 | Where located? | See matrix §3. |
| 7 | Connected to full-paper-cycle? | PDE + PAPER execution + validation + DPE: **yes**. Counterfactual research modules: **no**. Sell-all: **n/a**. |
| 8 | Minimal wiring if not connected? | See §6. |
| 9 | Smallest implementation if missing? | See §6 — mostly glue, not new engines. |

---

## 6. Minimal Wiring Plan (no new engines)

### P0 — Answer operator questions with existing data

1. **Sell-all scenario (read-only)**
   - Add a **report function** (not engine) reading `tae_accounting_snapshot.json`
   - Sum `open_positions_value + cash_available` → liquidation proceeds estimate
   - Optional: per-ticker unrealized → realized if sold at `current_price`
   - **No new sim engine** — arithmetic on existing accounting SSOT

2. **Execute PROMISING only**
   - Reorder cycle: `paper-decisions` → `paper-experiments` (validation) → `paper-execution`
   - Filter `tae_paper_execution.py` input by `decision_validation_results.json` where `verdict=PROMISING`
   - **Wiring only** — uses existing validation + execution

3. **Canonical vs PAPER comparator**
   - Read-only diff: `tae_accounting_snapshot.json` vs `paper_portfolio.json`
   - Report: cash delta, position count delta, per-ticker share delta, total value delta
   - Could live as section in `TAE_PAPER_EXECUTION_REPORT.md` or thin `tae_portfolio_comparison.py` wrapper
   - **No new portfolio engine**

4. **Counterfactual "what if TAE had executed"**
   - Already partially done: `paper_portfolio.json` IS the counterfactual executed state
   - Add snapshot-at-cycle-start from accounting + replay decisions chronologically (existing `execute_decision`)
   - Historical CF modules (`counterfactual_exit/entry`) remain separate for past-trade timing analysis

5. **Rule performance proof**
   - Join `rule_outcome_attribution.json` with `decision_validation_results.json` on `decision_id`
   - Rank rules by net simulated PnL + verdict alignment
   - Feed existing `tae_adaptive_paper_weights.py` (already partially wired)

### P1 — Optional reconnects (still no new engines)

- Wire `tae_decision_replay_composer` counterfactual section into PAPER execution report
- Expose `research_core/exit_analysis/counterfactual_exit.py` as `tae.py counterfactual-exit` read-only command
- Add `full-paper-cycle` summary field `canonical_vs_paper_delta` (data already in both JSONs)

---

## 7. Safety Classification

| Layer | Classification | Mutates live files? |
|---|---|---|
| `live_bot.py` | LOCAL_PAPER_RUNTIME | **Yes** — `portfolio.csv` (forbidden in TAE cycle) |
| `tae_paper_execution.py` | PAPER_ONLY | **No** — `runtime_outputs/paper_execution/` only |
| DPE executors | SHADOW_ONLY / PAPER_ONLY | **No** — isolated DPE dirs |
| PDE + validation | READ_ONLY | **No** |
| Counterfactual research | ANALYSIS_ONLY | **No** (reads `portfolio.csv`) |
| `outcome_evaluator.py` | LEGACY | **Yes** — `decision_registry.csv` |

**Audit validation (this run):**
- `python3 tae.py health` → NOT_READY (environmental; live_bot not running)
- `python3 tae.py full-paper-cycle` → **READY_WITH_WARNINGS**
- `git diff -- live_bot.py portfolio.csv live_signals.csv watchlist.txt core/ research_core/` → **0 diff lines**

---

## 8. Recommendation

**Do not build new engines.** The repo already contains:

- PAPER execution (`tae_paper_execution.py`) — integrated
- PROMISING validation (`run_paper_decision_validation`) — integrated but runs after execution
- Rule attribution — integrated to adaptive weights
- Counterfactual analysis — exists in research_core but not connected
- Sell-all — **only missing capability**; solvable with read-only accounting arithmetic

**Next step when approved:** minimal wiring pass (cycle reorder + PROMISING filter + portfolio diff report + sell-all snapshot). Estimated scope: 1–2 thin modules or report extensions, not a new execution engine.
