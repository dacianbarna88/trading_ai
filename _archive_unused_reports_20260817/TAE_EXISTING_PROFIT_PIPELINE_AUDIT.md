# TAE Existing Profit Pipeline Capability Audit

**Generated:** 2026-07-13  
**Mode:** READ_ONLY — no code changes, no commit  
**Machine-readable:** `tae_existing_profit_pipeline_audit.json`

---

## Final verdict

```text
PROFIT_PIPELINE_EXISTS_FRAGMENTED
```

---

## 1. Does a complete end-to-end profit pipeline view already exist?

**No.**

No command, module, dashboard section, or report traces the full chain in one operational view:

```text
market/scanner opportunity
  → signal
  → PDE final decision
  → decision-state / conflict gate
  → paper order
  → execution or block
  → trade
  → realized / unrealized PnL
  → decision validation / outcome
```

Repository search found **zero** matches for: `profit pipeline`, `opportunity funnel`, `decision funnel`, `execution funnel`, or `conversion` as a unified concept.

What **does** exist is a **fragmented** set of producers and partial reports, each covering 2–6 stages. The data to join them is largely already persisted (`decision_id`, `ticker`), but no consumer renders the full funnel.

---

## 2. If YES — (not applicable)

N/A — no complete view exists.

---

## 3. If PARTIAL — stage coverage

### Stage map

| Stage | Existing component | Command / entry | Output | In unified funnel? |
|-------|-------------------|-----------------|--------|-------------------|
| **Market / scanner opportunity** | `live_bot.py` scanner; `tae_growth_intelligence.py`; `tae_opportunity_cost_ledger.py`; `tae_intraday_discovery_engine.py` | `growth-intelligence`, `opportunity` | `tae_growth_intelligence.json`, `tae_opportunity_cost_ledger.json` | No — upstream analytics only |
| **Signal** | `live_signals.csv`; PDE `build_context()`; DPE `tae_decision_event_bus.py` `signal_snapshot` | `paper-decisions`, `dpe-events` | `live_signals.csv`, `decision_events.jsonl` | Partial — signal in PDE evidence / order `reason` text |
| **PDE final decision** | `tae_paper_decision_engine.py` `build_decision()` | `paper-decisions` | `runtime_outputs/paper_decisions/paper_decisions.json` | Yes (producer) |
| **Decision-state / conflict gate** | `tae_decision_state.py`, `tae_conflict_resolution.py`; PDE gates | `decision-state-refresh`, `conflict-resolution-refresh` | `active_decisions.json`, `conflicts.json` | Partial — `decision_switch_authorized` on decisions; `SKIPPED_SWITCH_NOT_AUTHORIZED` on orders |
| **Paper order** | `tae_paper_execution.py` `run_paper_execution()` | `paper-execution` | `paper_orders.jsonl` | Yes (producer) |
| **Execution or block** | `tae_paper_execution.py` `should_execute_decision()`, status writers | `paper-execution` | `TAE_PAPER_EXECUTION_REPORT.md` per-run stats | Yes (per-run only) |
| **Trade** | `tae_paper_execution.py` trade writers | `paper-execution` | `paper_trades.jsonl` | Yes (producer) |
| **Realized / unrealized PnL** | `paper_portfolio.json`, `mark_to_market.json`, `compare_canonical_vs_paper()` | `paper-execution`, `paper-mark-to-market`, `canonical-vs-paper` | portfolio + MTM JSON | Yes (aggregate / per-order) |
| **Decision validation / outcome** | `run_paper_decision_validation()`; `tae_longitudinal_outcome_memory.py`; `rule_outcome_attribution.json` | `paper-experiments`, `outcome-memory` | `decision_validation_results.json`, `decisions.jsonl`, attribution JSON | Partial — joined by `decision_id`, not in one report |

### Missing in any single view

1. Scanner/opportunity → signal conversion
2. Signal → PDE decision conversion
3. PDE → authorized execution conversion with block-reason rollup
4. Per-ticker timeline: signal → decision → order status → trade → PnL → validation verdict
5. `market_closed` as a PAPER execution block (session gating is **live_bot** only; PAPER execution does not emit `MARKET_CLOSED` skips)

### Is the gap only reporting / wiring?

**Yes.** Every stage has an active producer and persisted artifact. No stage lacks implementation. The defect is **consolidation and labelling**, not missing engines.

---

## Closest existing views (not complete)

### A. `python3 tae.py paper-execution` — best execution-stage view

| Item | Detail |
|------|--------|
| **File** | `tae_paper_execution.py` |
| **Functions** | `run_paper_execution()`, `validate_execution_run()`, `write_report()` |
| **Output** | `TAE_PAPER_EXECUTION_REPORT.md` |
| **Covers** | decisions consumed → orders_created / orders_executed / skipped_same_action / skipped_switch_not_authorized → trades_written → portfolio PnL |
| **Missing** | scanner, signal SSOT, decision-state detail, validation verdict, outcome attribution funnel |
| **Operational** | Yes — current report shows e.g. orders_created=3, skipped_same_action=22, trades_written=0 |

### B. `python3 tae.py outcome-memory` — best outcome-stage view

| Item | Detail |
|------|--------|
| **File** | `tae_longitudinal_outcome_memory.py` |
| **Functions** | `run_longitudinal_memory()`, `ingest_decisions()`, `checkpoint_snapshot()` |
| **Outputs** | `runtime_outputs/longitudinal_memory/decisions.jsonl`, `outcome_source_audit.json`, `TAE_LONGITUDINAL_MEMORY_REPORT.md` |
| **Covers** | PDE decision + validation verdict + promotion + order join at checkpoints + PnL outcome |
| **Missing** | signal origin, per-run funnel counts, block-reason taxonomy |
| **Operational** | Yes |

### C. `python3 tae.py full-paper-cycle` — orchestrator, not funnel

| Item | Detail |
|------|--------|
| **File** | `tae_structural_governance.py` |
| **Function** | `run_structural_paper_cycle()` |
| **Output** | `runtime_outputs/full_paper_cycle/summary.json`, `TAE_FULL_PAPER_CYCLE_REPORT.md` |
| **Covers** | runs all producers; `switch_blocked`, `skipped_switch_exec`, validation verdict counts, profit integrity |
| **Missing** | unified stage-by-stage conversion report |

### D. `python3 tae.py investment-council` — synthesis, not trace

| Item | Detail |
|------|--------|
| **File** | `tae_investment_council.py` |
| **Output** | `runtime_outputs/investment_council/council.json` |
| **Covers** | post-hoc operator brief from decisions, attribution, governance |
| **Missing** | execution funnel, trade trace, signal origin |

### E. DPE chain — parallel shadow path

`dpe-events` → `dpe-splitter` → `dpe-competitive` / `dpe-collaborative` includes `signal_snapshot` in events but traces **philosophy experiment jobs**, not PDE → `paper_orders` → `paper_trades`.

### F. Live-only shadow path

`research_core/governance/shadow_validation_ledger.py` + dashboard Command Center **Shadow Validation** panel trace **live BUY** signal → TAE advisory block (`BUY_BLOCKED_BY_TAE`). This is **not** the PAPER PDE execution pipeline.

---

## Key field / status inventory (found in repo)

| Field / concept | Where persisted |
|-----------------|-----------------|
| `orders_created` | `tae_paper_execution.py` run stats, `TAE_PAPER_EXECUTION_REPORT.md` |
| `orders_executed` | same |
| `trades_written` | same; DPE executor metrics |
| `skipped_same_action` | same |
| `skipped_no_mark_price` | order `status` = `SKIPPED_NO_MARK_PRICE` in `paper_orders.jsonl` |
| `skipped_switch_not_authorized` | order `status`; `tae_full_paper_cycle.py` summary count |
| `block_reason` | `tae_shadow_validation_events.csv` (live); governance `block_reasons` (structural) |
| `missed_opportunity` / `opportunity_cost` | GII, opportunity ledger, longitudinal memory |
| `rule_attribution` | `rule_outcome_attribution.json`; `build_rule_attribution()` |
| `decision_validation` | `decision_validation_results.json` via `run_paper_decision_validation()` |

Example order row (join hub): `paper_orders.jsonl` carries `decision_id`, `status`, `executed`, `realized_pnl`, `rule_sources`, and signal text inside `reason` (e.g. `signal=STRONG BUY score=100.0`).

---

## Dashboard coverage

| Surface | File | Pipeline coverage |
|---------|------|-------------------|
| TAE Command Center | `dashboard_tae_command_center.py` | Artifact health, live shadow BUY funnel, DPE panels, execution integrity — **no PDE→trade funnel** |
| Performance tab | `dashboard_v2.py` | Canonical + PAPER portfolio values — **no stage funnel** |
| Portfolio tab | `dashboard_v2.py` | `portfolio.csv` legacy — not PAPER decision trace |

---

## 4. If NO — proof no equivalent exists

While the verdict is PARTIAL (not NO), exhaustive search confirms:

- No CLI command named or documented as profit/decision/execution funnel
- No `TAE_*` report titled or structured as end-to-end profit pipeline
- No dashboard section labelled as profit pipeline conversion
- No callable `trace_profit_pipeline()` or equivalent function
- `TAE_FULL_LOGIC_MAP.md` documents a **closed loop** of research stages (GII → PDE → validation → learning) but **not** signal→execution conversion metrics

---

## Smallest reuse / consolidation path (reporting only)

No new engine required. Minimal read-only join on existing keys:

1. **SSOT execution ledger:** `runtime_outputs/paper_execution/paper_orders.jsonl` (`decision_id`)
2. **Join PDE:** `paper_decisions.json` → action, confidence, `decision_switch_authorized`
3. **Join validation:** `decision_validation_results.json` → verdict, `profit_delta`
4. **Join signal (optional):** `live_signals.csv` on `ticker`
5. **Join attribution:** `rule_outcome_attribution.json` on `rule_sources` from orders
6. **Emit via:** extend `tae_paper_execution.write_report()` or add read-only section to `tae_morning_operational_audit.py` — reuse `tae_longitudinal_outcome_memory.load_orders_by_decision()` pattern

Closest callables to orchestrate without new modules:

- `tae_paper_execution.run_paper_execution`
- `tae_dpe_paper_executor_infra.run_paper_decision_validation`
- `tae_longitudinal_outcome_memory.run_longitudinal_memory`

---

## Tests referencing funnel-like fields

- `tae_paper_execution_test.py` — `orders_created`, `trades_written`, `SKIPPED_NO_MARK_PRICE`
- `tae_full_paper_cycle_test.py` — `SKIPPED_SWITCH_NOT_AUTHORIZED` aggregation

No test asserts a complete end-to-end profit pipeline report exists.

---

## Summary answers

| # | Answer |
|---|--------|
| 1 | Complete end-to-end view: **NO** |
| 2 | N/A |
| 3 | **PARTIAL** — all stages have producers; missing unified funnel report and conversion metrics; gap is **reporting/wiring only** |
| 4 | Proven by repo-wide search + CLI inventory: no equivalent single view |
| 5 | No new engine proposed |
| 6 | Smallest path: join existing JSON/JSONL on `decision_id` / `ticker`; reuse `paper-execution` report or `morning-audit` as read-only consumer |
