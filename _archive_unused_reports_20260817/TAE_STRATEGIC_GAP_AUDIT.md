# TAE Strategic Gap Audit

**Date:** 2026-07-05  
**Mode:** READ ONLY — no implementation, no architecture changes, no commit  
**Authority:** `PROJECT_BOOK.md`, `TAE_MASTER_CONTEXT.md`, `TAE_DEVELOPMENT_PROTOCOL.md`, repository state at X.Decision checkpoint (`50ebc0b`)

---

## Executive finding

Between the current TAE ecosystem and the target architecture, **one capability** dominates all remaining gaps:

**X.10 — Live Advisory Outcome Attribution (forward PnL / counterfactual closure on blocked vs allowed BUYs)**

The live spine already intervenes (`RISK_ADVISORY` blocks new BUY) and already observes (`tae_shadow_validation_events.csv`), but **cannot yet measure whether those interventions improved or harmed realized profit**. Every other remaining item depends on this closed loop or is explicitly deferred until it exists.

---

## 1. What is the target architecture?

The target is a **paper-only, evidence-gated trading intelligence organism** with three converging layers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ LIVE SPINE (execution + single gate)                                    │
│   watchlist → live_bot → portfolio.csv / live_signals.csv               │
│   live_bot reads tae_live_advisory.json → RISK_ADVISORY blocks new BUY  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CONNECTED OBSERVABILITY (live decisions logged)                         │
│   shadow_validation_ledger → tae_shadow_validation_events.csv           │
│   → summary / counterfactual reports (outcome attribution REQUIRED)     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ SHADOW VALIDATION STACK (market-open, SHADOW_ONLY)                      │
│   intraday fade → protect → cooldown → replay → confidence → knowledge  │
│   → decision governor VIEW (posture, NOT live execution)                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ EVIDENCE-GATED PROMOTION (no auto-live)                                 │
│   Prove counterfactuals improve realized PnL → operator/architect review│
│   → optional future live policy change (never auto from reports)      │
└─────────────────────────────────────────────────────────────────────────┘
```

**Strategic objective** (all canonicals): improve **realized profit quality** (exit timing, re-entry discipline, decision sequencing) using shadow and live-connected evidence **before** any live rule change.

**Operating constraints** (mandatory): `ANALYSIS_ONLY` · `PAPER_ONLY` · `NO_BROKER` · `NO_EXECUTION`. TAE surrounds `live_bot.py`; it does not become an execution engine.

**Promotion rule** (`TAE_PERFORMANCE1_PROFIT_GROWTH_ARCHITECTURE.md`, `PROJECT_BOOK.md` §12): no live change until shadow validators produce converging evidence **and** live-connected outcome attribution validates that interventions (especially BUY blocks) actually improve or protect realized PnL. Governor-informed live blocking remains **not approved** until that evidence exists.

---

## 2. Which strategic capabilities are COMPLETE?

| Capability | Evidence |
|------------|----------|
| **Canonical live execution spine** | `live_bot.py` → `live_signals.csv`, `portfolio.csv`; protected and unchanged at checkpoint |
| **Single live BUY risk gate (X.8)** | `live_advisory_runtime.py` reads `tae_live_advisory.json`; `RISK_ADVISORY` blocks new BUY only; SELL untouched |
| **Advisory aggregation & bridge (X.7B–X.7C)** | `advisory_index.py` → `tae_advisory_index.json`; `live_advisory_bridge.py` → `tae_live_advisory.json` |
| **Governor enrichment in advisory (X.DECISION-2B)** | `governor_enrichment` in advisory JSON — informational only; does not change `block_new_buy` |
| **Connected shadow BUY observability (X.9)** | `shadow_validation_ledger.py` append-only events; `tae_shadow_validation_report.py` → summary JSON |
| **Shadow validation event accumulation** | `tae_shadow_validation_events.csv` populated (660+ events referenced in live advisory counterfactual context) |
| **Market-open shadow stack (11 steps)** | `tae_market_open_intelligence_runner.py`: infra → fade → protect → cooldown → replay → confidence → knowledge → governor |
| **Decision replay composer (X.REPLAY-1)** | `tae_decision_replay_composer.py` → `tae_decision_replay.json` |
| **Knowledge base VIEW (X.KNOWLEDGE-1A–1C)** | `tae_knowledge_base.py`, `tae_confidence_evolution.py` — materialized views, not execution |
| **Decision governor VIEW (X.DECISION-1/2A)** | `tae_decision_governor.py` — reads upstream JSON only; SHADOW_ONLY |
| **Infrastructure health audit** | `tae_infrastructure_health.py` — permission-safe subprocess handling (X.INFRA-HEALTH-1/2) |
| **PnL / accounting SSOT** | `tae_accounting_snapshot.json` via accounting snapshot pipeline |
| **Full ecosystem batch research** | `tae_full_ecosystem_run.py` / orchestrator — evidence, ranking, registry (report-only) |
| **Dashboard TAE visibility (X.7A)** | `dashboard_v2.py` TAE Intelligence Reports + advisory display |
| **Unified runtime SSOT reader** | `tae_unified_runtime.json` feeds bridge and enrichers |
| **Development governance** | `TAE_DEVELOPMENT_PROTOCOL.md`, checkpoint script, canonical doc sync |

**Classification at checkpoint:** `CONTROLLED_RUNTIME_INTEGRATION` (X.8) + `CONNECTED_OBSERVABILITY` (X.9) + `SHADOW_DECISION_VIEWS` (X.Decision).

---

## 3. Which strategic capabilities are PARTIAL?

| Capability | Current state | Gap |
|------------|---------------|-----|
| **Outcome tracking / attribution (X.10)** | Events logged; summary hardcodes `outcome_tracking_status: PENDING_NEXT_PHASE` | No forward PnL, avoided-loss, or missed-gain attribution on `BUY_BLOCKED_BY_TAE` vs `BUY_ALLOWED` |
| **Counterfactual runtime / outcome memory** | Bridge emits `outcome=PENDING_NEXT_PHASE`; unified runtime `Outcome_Memory: PENDING_NEXT_PHASE` | No batch closure from live events to counterfactual outcomes |
| **Event memory ingestion** | Scaffold exists; 0 live events ingested | No news/event-driven advisory enrichment |
| **Governor-informed live blocking** | Governor VIEW operational; enrichment informational | Not wired to `block_new_buy` — **by design**, pending evidence |
| **Shadow gate convergence** | Replay/knowledge/governor produce postures; some upstream gates report NOT_READY/WATCH | Readiness is diagnostic; not yet tied to validated live intervention outcomes |
| **Governed watchlist promotion** | Tools and audits exist; no full promotion/rollback UI | `TAE_IMPLEMENTATION_ROADMAP.md` DASH-003 deferred |
| **Historical profit validators (PROTECT-2 lineage)** | PROTECT-1 snapshot + replay/knowledge stack built | PERFORMANCE-1 historical validators partially superseded by X.REPLAY/knowledge path; live-connected proof still missing |
| **Legacy outcome engines** | Root-level `outcome_assignment_engine.py`, `historical_outcome_tracker.py`, etc. | V14/V28-era; not connected to X.9 event schema or live advisory loop |

---

## 4. Which ONE missing capability currently limits TAE the most?

**X.10 — Live Advisory Outcome Attribution for blocked vs allowed BUYs**

Specifically: a read-only batch capability that joins `tae_shadow_validation_events.csv` with forward portfolio/signal marks (and optionally accounting snapshot) to produce attributed outcomes — avoided loss, missed gain, net intervention value — and advances `outcome_tracking_status` beyond `PENDING_NEXT_PHASE`.

Roadmap names this `tae_shadow_outcome_capture.py` → `tae_shadow_validation_outcomes.json` (`TAE_IMPLEMENTATION_ROADMAP.md` Phase 3, item F). Canonical sprint ID: **X.10**.

---

## 5. Why is this capability more important than every other remaining item?

1. **The live control loop is open.** X.8 already changes live behavior (blocks BUY). X.9 already records those decisions. Without attribution, TAE is intervening in real paper trading **blind** — the system cannot answer its own strategic question: *did blocking this BUY improve realized profit quality?*

2. **It is the live-connected proof layer PERFORMANCE-1 requires.** The shadow stack detects exit evaporation, re-entry churn, and sequencing failures, but the canonical verdict is: *"does not yet prove which counterfactual would have improved realized PnL over time."* X.10 closes that proof loop on the **live-connected** path where intervention already happens.

3. **It unblocks every downstream promotion decision.** Tightening the X.8 gate, wiring governor postures to live blocking, promoting knowledge findings, or changing advisory thresholds all require evidence that past blocks were net beneficial. Without X.10, those remain **architecturally forbidden** (`PROJECT_BOOK.md` §12, `SESSION_START.md`).

4. **Data is already accumulating with zero extracted value.** Events exist; advisory counterfactual context already references them with `outcome=PENDING_NEXT_PHASE`. The bottleneck is not collection — it is **measurement**.

5. **It ranks above adjacent gaps:**
   - **Governor live blocking** — consequence of X.10, not prerequisite; unsafe without attribution.
   - **Event memory ingestion** — enriches advisory inputs; does not validate whether current gate works.
   - **Dashboard / watchlist UI** — operational visibility; does not close the profit-quality feedback loop.
   - **Shadow NOT_READY gates** — shadow diagnostics; live gate is already active regardless of governor readiness.
   - **Legacy outcome engines** — wrong schema and era; not a substitute for X.9-connected attribution.

6. **Unanimous canonical priority.** `PROJECT_BOOK.md` §12, `SESSION_START.md`, `TAE_MASTER_CONTEXT.md`, and `PROJECT_STATUS.md` all designate X.10 as the **next approved sprint** with explicit prerequisite (accumulated ledger events — already satisfied).

---

## 6. Can it be built by extending existing modules?

**Yes.**

X.10 is a **read-only batch extension** of the X.9 observability layer. It does not require a new execution path, a new live gate, or changes to `live_bot.py` trading logic. The roadmap explicitly scopes it as: read events + forward marks → outcomes JSON → update status fields in summary/advisory context.

No new architectural tier is required — only the missing **closure step** in the existing LIVE → OBSERVE → **MEASURE** chain.

---

## 7. Which existing modules would be reused?

| Module / artifact | Reuse role |
|-------------------|------------|
| `research_core/governance/shadow_validation_ledger.py` | Event schema, `BUY_BLOCKED_BY_TAE` / `BUY_ALLOWED` types, CSV fieldnames |
| `tae_shadow_validation_events.csv` | Primary input SSOT (X.9 ledger output) |
| `tae_shadow_validation_report.py` | Summary aggregation pattern; `outcome_tracking_status` field to advance |
| `tae_shadow_validation_summary.json` | Downstream consumer of attribution status |
| `portfolio.csv` | Read-only forward marks / position state after event timestamp |
| `live_signals.csv` | Read-only price/score context at evaluation and forward windows |
| `research_core/governance/live_advisory_bridge.py` | Existing `_load_counterfactual_summary()` / counterfactual reason lines — consume outcomes when ready |
| `tae_unified_runtime.json` | `Outcome_Memory` section — transition from `PENDING_NEXT_PHASE` |
| `research_core/accounting/accounting_snapshot` / `tae_accounting_snapshot.json` | Realized PnL cross-check where applicable |
| `core/portfolio_prices.py` or yfinance read patterns (read-only) | Forward price marks if not inferable from CSV alone |
| `research_core/meta_intelligence/recommendation_outcome_engine.py` | Reference pattern for batch outcome assignment (different domain; do not duplicate pipeline) |

**Integration point:** batch job invoked after market cycles (roadmap: `python3 tae_shadow_outcome_capture.py --dry-run`); feeds summary JSON and advisory counterfactual context — **no live_bot changes**.

---

## 8. What should explicitly NOT be built because it already exists?

| Do NOT rebuild | Already exists |
|----------------|----------------|
| Second BUY event logger | `shadow_validation_ledger.py` (X.9) |
| Second live↔TAE advisory bridge | `live_advisory_bridge.py` (X.7C + X.DECISION-2B) |
| Second live BUY blocker / inline JSON parsing in `live_bot.py` | `live_advisory_runtime.py` (X.8) |
| Second shadow validation summary aggregator | `tae_shadow_validation_report.py` |
| Second decision governor or live decision engine | `tae_decision_governor.py` (SHADOW_ONLY VIEW) |
| Parallel market-open orchestrator | `tae_market_open_intelligence_runner.py` |
| Greenfield knowledge SSOT | `tae_knowledge_base.py` (VIEW) |
| Second replay pipeline | `tae_decision_replay_composer.py` |
| New master runner / daily chain | `ecosystem_orchestrator.py`, `tae_full_ecosystem_run.py` |
| V14-era outcome assignment on `decision_registry.csv` | Legacy scripts — wrong SSOT for Phase X live loop |
| Auto-promotion from ranking/meta evolution to live | Explicitly forbidden by protocol and PROJECT_BOOK §12 |

**Before any new file:** grep `research_core/`, confirm against `PROJECT_BOOK.md` §11 anti-duplication table, and extend the X.9 → X.10 batch path rather than introducing a parallel outcome pipeline.

---

## Summary matrix

| Question | Answer |
|----------|--------|
| Target | Evidence-gated paper trading organism: live spine + single BUY gate + shadow stack + **closed outcome loop** before promotion |
| Complete | Live bot, X.8 gate, X.9 ledger, advisory stack, shadow stack, governor/knowledge VIEWs, infra health |
| Partial | Outcome attribution, counterfactual memory, event memory, governor live wiring, governed promotion UI |
| **#1 gap** | **X.10 — Live advisory outcome attribution (blocked vs allowed BUY forward PnL)** |
| Why #1 | Live loop intervenes without proof; blocks all evidence-gated promotion; data already collected |
| Extendable? | Yes — read-only batch on existing X.9 artifacts |
| Reuse | `shadow_validation_ledger`, events CSV, validation report, portfolio/signals CSVs, advisory bridge, accounting snapshot |
| Do not rebuild | Ledger, gate, bridge, governor engine, orchestrator duplicates, legacy outcome engines |

---

*End of TAE_STRATEGIC_GAP_AUDIT.md*
