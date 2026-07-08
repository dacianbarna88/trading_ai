# TAE Dual Philosophy Execution Engine (DPE) — Architecture v1

**Sprint:** DPE v1 — Architecture Only  
**Date:** 2026-07-07  
**Status:** DESIGN — NOT IMPLEMENTED  
**Mode:** READ_ONLY architecture · NO_BROKER · NO_REAL_EXECUTION · NO_PORTFOLIO_CHANGE · NO_LIVE_BOT_CHANGE · NO_COMMIT  
**Machine-readable:** `tae_dual_execution_architecture.json`

---

## Mission

TAE must stop comparing philosophy **scores** only. TAE must compare philosophy **performance**.

The market becomes the referee through continuous A/B paper experimentation:

- **Competitive Execution (Paper)** — independent portfolio, PnL, statistics  
- **Collaborative Execution (Paper)** — independent portfolio, PnL, statistics  
- **Winner Selection** — market-derived, not human opinion  

This document defines the execution architecture. **No execution code is implemented in this sprint.**

---

## Principle

| Today | Target |
|-------|--------|
| Market → Analytics → Philosophy scores | Market → Decision Point → Dual paper executors → Independent PnL → Winner → Learning |

Philosophy Lab v1 (`tae_market_philosophy_lab.py`) answers: *"Which philosophy fits this snapshot?"*  
DPE answers: *"Which philosophy **performed better** over time?"*

---

## Architecture diagram

```text
                         ┌─────────────────────┐
                         │   MARKET / PRICES   │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   live_bot.py       │  ← UNCHANGED (observe / canonical live)
                         │   portfolio.csv     │  ← REAL SSOT — never touched by DPE
                         └──────────┬──────────┘
                                    │ Decision Event (read-only tap)
                         ┌──────────▼──────────┐
                         │  DECISION EVENT BUS │  Phase 2
                         │  decision_events    │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
   ┌──────────▼─────────┐           │          ┌──────────▼─────────┐
   │ EXECUTION SPLITTER │◄──────────┘          │  GII + Targets +   │
   │  + philosophy ctx  │                      │  Philosophy Lab    │
   └──────────┬─────────┘                      └────────────────────┘
              │
     ┌────────┴────────┐
     │                 │
┌────▼─────┐     ┌─────▼────┐
│COMPETITIVE│     │COLLABOR- │
│ EXECUTOR │     │  ATIVE   │
│ Phase 3  │     │ EXECUTOR │
└────┬─────┘     │ Phase 4  │
     │           └─────┬────┘
┌────▼─────┐     ┌─────▼────┐
│ PAPER    │     │ PAPER    │
│ PORT A   │     │ PORT B   │
│ isolated │     │ isolated │
└────┬─────┘     └─────┬────┘
     │                 │
     └────────┬────────┘
              │
   ┌──────────▼──────────┐
   │  METRICS ENGINE     │  Phase 5
   │  daily / weekly /   │
   │  monthly            │
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  RESULT EVALUATOR   │  Market referee
   │  winner selection   │
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  LEARNING ENGINE  │  Phase 6
   │  (no auto-live)   │
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │ ADAPTIVE PHILOSOPHY │  Phase 7 — design only
   │ recommendation      │
   └─────────────────────┘
```

---

## 1. Current execution flow

```text
watchlist.txt
    ↓
live_bot.py                    ← ONLY live trade writer
    ↓
core/trades.py, core/trailing.py
    ↓
portfolio.csv + live_signals.csv   ← REAL SSOT
    ↓
tae_accounting_snapshot.json       ← derived read-only
    ↓
(parallel, on-demand)
tae.py protect → shadow → PIB → memory → committee → learning → context → PDG
tae.py portfolio-protect → PPG
tae.py policy → APPE
tae.py growth-analytics → opportunity → winner → growth-intelligence → profit-targets
tae.py philosophy                     ← scores only, no performance track
```

**Gap:** Philosophy comparison is static and score-based. No parallel paper arms with independent PnL history.

---

## 2. Future execution flow

```text
live_bot.py (unchanged Phases 1–6)
    ↓
Decision Event Bus              ← tap signals/trades log, not intercept live execution
    ↓
Execution Splitter              ← attach GII + targets + philosophy lab context
    ↓
┌─────────────────┬─────────────────┐
│ Competitive     │ Collaborative   │
│ Executor        │ Executor        │
└────────┬────────┴────────┬────────┘
         ↓                   ↓
   Paper Portfolio A    Paper Portfolio B
   runtime_outputs/     runtime_outputs/
   dpe/paper_competitive/ dpe/paper_collaborative/
         ↓                   ↓
   Daily Metrics Engine (both arms)
         ↓
   Weekly / Monthly rollups
         ↓
   Result Evaluator → Winner Selection
         ↓
   Learning Engine → DPE Learning Ledger
         ↓
   Adaptive Philosophy Engine → shadow recommendation ONLY
```

**Phase 7 (future):** Optional read-only advisory enrichment — never auto-wires to live_bot without governance sprint.

---

## 3. Portfolio isolation

| Store | Path | Owner | DPE may write? |
|-------|------|-------|----------------|
| Real portfolio | `portfolio.csv` | `live_bot.py` | **NEVER** |
| Real signals | `live_signals.csv` | `live_bot.py` | **NEVER** |
| Paper competitive | `runtime_outputs/dpe/paper_competitive/portfolio.csv` | DPE competitive executor | YES (paper only) |
| Paper collaborative | `runtime_outputs/dpe/paper_collaborative/portfolio.csv` | DPE collaborative executor | YES (paper only) |
| Real accounting | `tae_accounting_snapshot.json` | accounting derive | **NEVER** (read benchmark) |
| Paper accounting | `tae_dpe_accounting_competitive.json` / `_collaborative.json` | DPE metrics | YES |

**Isolation rules:**

1. Paper paths must pass prefix guard: `runtime_outputs/dpe/` only  
2. No symlinks from paper → real portfolio  
3. Initial seed: one-time copy of portfolio snapshot at experiment start — then fork  
4. Competitive and collaborative portfolios never cross-write  
5. Executors run with `DPE_ENABLED` feature flag — default **false**

---

## 4. Metrics catalog

Both philosophies compute the **same metric set** for fair A/B comparison.

### Return & PnL

| Metric | Definition |
|--------|------------|
| Total Return | (current equity − starting equity) / starting equity |
| Realized Profit | Closed trade PnL USD |
| Unrealized Profit | Mark-to-market open positions |
| Profit Capture | Realized + unrealized vs theoretical peak (reuse GA formula on paper store) |
| Opportunity Cost | Peak − captured (reuse ledger concept on paper history) |

### Risk

| Metric | Definition |
|--------|------------|
| Drawdown | Max peak-to-trough equity % |
| Win Rate | Winning trades / total closed |
| Average Winner / Loser | Mean USD per win/loss |
| Sharpe | Return / volatility (session or rolling) |
| Sortino | Return / downside deviation |
| Recovery | Return / max drawdown |
| Max Adverse Excursion (MAE) | Worst intra-trade drawdown |
| Max Favorable Excursion (MFE) | Best intra-trade peak |

### Quality & behavior

| Metric | Definition |
|--------|------------|
| Capital Efficiency | Return / average capital deployed |
| Profit Factor | Gross wins / gross losses |
| Average Holding Time | Mean hours per closed position |
| Market Harmony Score | From philosophy lab inputs applied to paper outcomes |
| Stress Score | Drawdown + collapse events + policy breach count |
| Consistency Score | Rolling variance of session returns (inverse) |
| Philosophy Adherence | % decisions matching arm's intended posture |

### Aggregation cadence

| Cadence | Output artifact |
|---------|-----------------|
| Daily (session) | `tae_dpe_daily_metrics.json` |
| Weekly (5 sessions) | `tae_dpe_weekly_metrics.json` |
| Monthly | `tae_dpe_monthly_metrics.json` |

---

## 5. Learning loop

```text
End of session
    ↓
Collect competitive metrics (arm A)
Collect collaborative metrics (arm B)
    ↓
Result Evaluator.compare()
    ↓
Declare winner: COMPETITIVE | COLLABORATIVE | TIE | INCONCLUSIVE
    ↓
Learning Engine.append_episode()
    → tae_dpe_learning_ledger.json
    ↓
Adaptive Philosophy Engine.recommend()
    → tae_dpe_adaptive_recommendation.json
    ↓
Governance / human review (required before any live influence)
```

**Hard rule:** Learning outputs do **not** automatically change `live_bot.py`, `portfolio.csv`, or `tae_live_advisory.json`.

Winner selection criteria (multi-metric, configurable weights):

1. Risk-adjusted return (Sortino primary)  
2. Profit capture rate  
3. Opportunity cost (lower wins)  
4. Drawdown (lower wins)  
5. Consistency score  

Minimum sessions before winner declared: **5** (configurable in `tae_dpe_config.json`, Phase 2).

---

## 6. Adaptive philosophy (design only)

TAE eventually learns regime-dependent dominance:

| Regime signal | Likely dominant arm | Adaptive state |
|---------------|---------------------|----------------|
| LOW_RISK + strong keep-growing | Competitive | COMPETITIVE_DOMINANT |
| HIGH_RISK + high missed + context weakening | Collaborative | COLLABORATIVE_DOMINANT |
| Alternating session wins | Neither stable | HYBRID (50/50 paper weight) |
| Insufficient sessions | — | INCONCLUSIVE |

**Adaptive engine inputs:**

- Rolling winner history (last N sessions)  
- APPE policy state trend  
- Market harmony score trend  
- Capture rate trend (paper vs real benchmark)

**Adaptive engine outputs:**

- Recommended experiment mode: PAPER_COMPETITIVE | PAPER_COLLABORATIVE | PAPER_MIXED  
- Suggested weight split for hybrid (e.g. 70/30)  
- Confidence and explanation  

**Not in scope v1:** Automatic live philosophy switching.

---

## 7. Safety architecture

| Control | Implementation |
|---------|----------------|
| Paper only | All DPE writes under `runtime_outputs/dpe/` |
| No broker | Executors simulate fills from price snapshots |
| No real money | Separate paper cash ledger |
| No live changes Phases 1–6 | `live_bot.py` read-only tap |
| Feature flags | `DPE_ENABLED`, `DPE_*_ARM`, `DPE_LIVE_GATE` (always false until governance) |
| Rollback | Disable flag; delete or archive `runtime_outputs/dpe/` |
| Independent storage | No shared mutable state with real SSOT |
| Audit trail | `decision_events.jsonl` append-only log |

---

## 8. Reuse audit — NO duplication

DPE **consumes** existing SSOT. DPE **does not reimplement** upstream logic.

| Existing module | Artifact | DPE role | Duplicated? |
|-----------------|----------|----------|-------------|
| Growth Intelligence | `tae_growth_intelligence.json` | Splitter context, per-ticker scores | **NO** |
| Growth Analytics | `tae_profit_growth_analytics.json` | Capture benchmark | **NO** |
| Opportunity Ledger | `tae_opportunity_cost_ledger.json` | Collaborative cost metric | **NO** |
| Winner Lifecycle | `tae_winner_lifecycle_profiler.json` | Collaborative exit rules | **NO** |
| Profit Target Adapter | `tae_profit_target_adapter.json` | Competitive numeric targets | **NO** |
| Philosophy Lab | `tae_market_philosophy_lab.json` | Initial arm bias seed | **NO** — scores ≠ performance |
| PPG | `tae_portfolio_profit_governor.json` | Collaborative portfolio constraint | **NO** |
| APPE | `tae_adaptive_profit_policy_engine.json` | Policy alignment | **NO** |
| Memory | `tae_profit_memory_engine.json` | Episode format reference | **NO** — separate DPE ledger |
| Context | `tae_profit_context_engine.json` | PCE gates collaborative arm | **NO** |
| Committee | `tae_profit_decision_committee.json` | Optional collaborative veto read | **NO** |
| Accounting | `tae_accounting_snapshot.json` | Real benchmark read-only | **NO** |

**New DPE-only modules (future phases):**

- `tae_dpe_decision_splitter.py`  
- `tae_dpe_competitive_executor.py`  
- `tae_dpe_collaborative_executor.py`  
- `tae_dpe_metrics_engine.py`  
- `tae_dpe_result_evaluator.py`  
- `tae_dpe_learning_engine.py`  
- `tae_dpe_adaptive_engine.py`  

**Forbidden to modify:** `live_bot.py`, `core/`, all upstream growth/protection engines listed above.

---

## 9. Future roadmap

| Phase | Name | Deliverable | Live impact |
|-------|------|-------------|-------------|
| **1** | **Architecture** | This doc + JSON + report | **None** |
| 2 | Execution Splitter | Event bus + splitter + schema | None |
| 3 | Competitive Executor | Paper arm A | None |
| 4 | Collaborative Executor | Paper arm B | None |
| 5 | Daily/Weekly/Monthly Evaluator | Metrics + winner selection | None |
| 6 | Learning | DPE learning ledger | None |
| 7 | Adaptive Execution | Recommendation engine + live gate **design review** | Governance only |

**CLI (future):** `python3 tae.py dpe-experiment` — runs paper pipeline when `DPE_ENABLED=true`.

---

## Component specifications

### Decision Event

Normalized record emitted when live_bot (or replay) produces a tradable decision:

```json
{
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "ticker": "MRK",
  "event_type": "SIGNAL | FILL | EOD_MARK",
  "live_action": "BUY | SELL | HOLD",
  "price": 0.0,
  "source": "live_bot_log | replay"
}
```

### Execution Splitter

Enriches event with philosophy packets:

- **Competitive packet:** growth_score, target partial/trailing, KEEP_GROWING bias  
- **Collaborative packet:** harmony score, PCE verdict, lifecycle stage, protect bias  

### Competitive Executor rules (paper)

- Prefer HOLD / extend winners when GII strategy = KEEP_GROWING_SHADOW  
- Apply `dynamic_partial_tp_pct` from profit target adapter  
- Wider trailing vs collaborative  
- Accept higher drawdown for upside (alpha-first)

### Collaborative Executor rules (paper)

- Respect PCE PROTECT_NOW / CONTEXT_WEAKENING — exit or reduce  
- Tighter trailing when lifecycle WEAKENING / PROFIT_DECAY  
- Honor APPE CAPITAL_PRESERVATION when HIGH_RISK  
- Lower opportunity cost priority over raw upside

---

## Storage layout

```text
runtime_outputs/dpe/
├── decision_events.jsonl
├── paper_competitive/
│   ├── portfolio.csv
│   ├── trades.jsonl
│   └── state.json
├── paper_collaborative/
│   ├── portfolio.csv
│   ├── trades.jsonl
│   └── state.json
└── sessions/
    └── YYYY-MM-DD/
        ├── competitive_metrics.json
        └── collaborative_metrics.json

tae_dpe_daily_metrics.json
tae_dpe_weekly_metrics.json
tae_dpe_monthly_metrics.json
tae_dpe_winner_selection.json
tae_dpe_learning_ledger.json
tae_dpe_adaptive_recommendation.json
tae_dpe_config.json                    ← feature flags, Phase 2
```

---

## Migration strategy

1. **This sprint:** Publish architecture — zero runtime change  
2. **Phase 2:** Add `tae_dpe_config.json` with all flags false  
3. **Phase 2:** Splitter reads `bot_output.log` / decision replay — no `live_bot.py` edit  
4. **Phase 3–4:** Seed paper portfolios from one-time snapshot; fork immediately  
5. **Phase 5:** Run ≥5 sessions before trusting winner selection  
6. **Phase 7:** Separate governance sprint for any live advisory enrichment  

---

## Rollback strategy

| Scenario | Action |
|----------|--------|
| DPE misbehaves | Set `DPE_ENABLED=false` |
| Corrupt paper data | Delete `runtime_outputs/dpe/` |
| Bad learning entries | Truncate `tae_dpe_learning_ledger.json` |
| Live impact concern | Phases 1–6 have **no live path** — nothing to roll back on live |

---

## Relationship to Philosophy Lab v1

| Layer | Question | Output |
|-------|----------|--------|
| Philosophy Lab v1 | Who *should* win on this snapshot? | competitive_score vs collaborative_score |
| DPE | Who *did* win over sessions? | paper PnL, capture, drawdown, winner arm |

Lab informs splitter **initial bias**. DPE **validates** bias with performance.

Current lab verdict (2026-07-07): COLLABORATIVE_MODEL wins on scores — DPE will test if that holds on paper PnL.

---

## Open questions (Phase 2 resolution)

1. Event source: tap `bot_output.log` vs structured hook (prefer log tap to avoid live_bot change)  
2. Fill simulation: last price vs bid/ask spread model  
3. Starting capital for paper arms: mirror real equity or fixed notional  
4. Hybrid arm: single executor with weight blend vs two pure arms only (recommend two pure arms first)  

---

## Summary

DPE is the architectural bridge from **philosophy scoring** to **philosophy performance measurement**. It extends the Profit Growth stack without duplicating it, keeps real execution isolated, and lets the market referee through measurable paper outcomes.

**Next sprint after Phase 1:** Philosophy Lab v2 — Paper Experiment Design (Splitter schema + first replay harness).
