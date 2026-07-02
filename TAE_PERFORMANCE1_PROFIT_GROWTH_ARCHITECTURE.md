# TAE PERFORMANCE-1 — Profit Growth Diagnostic & Decision Architecture

**Date:** 2026-07-02  
**Status:** DESIGN ONLY — no implementation  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Question answered:** *Why is profit not growing despite good ticker selection, and what mechanism would have improved the outcome?*

---

## Executive summary

Recent audit shows TAE’s bottleneck is **not discovery** — it is **decision quality after entry**:

| Symptom | Observed magnitude |
|---------|-------------------|
| Intraday profit evaporation | Current unrealized ~ **-33 USD** vs theoretical at high ~ **+453 USD** |
| Missed opportunity | ~ **+486 USD** on open positions |
| Re-entry churn | **BUY → STOP → BUY → STOP** on MU, PM, LLY, MC.PA |
| Score persistence after STOP | MU / LLY → STRONG BUY 100; PM → STRONG BUY 80 |

Existing shadow stack (X.INTRADAY, X.KNOWLEDGE-1A, X.PROTECT-1) **detects** these patterns but does **not yet prove** which counterfactual would have improved realized PnL over time, nor which failure mode dominates (exit, re-entry, or entry timing).

This document defines three future modules plus downstream knowledge evolution — all **read-only, SHADOW_ONLY**, writing reports only.

**Verdict:** **BUILD** — start with **X.PROTECT-2**.

---

## Problem decomposition

```
Good ticker found
       │
       ▼
   ENTRY (BUY) ─────────────────────────────► Entry too early?
       │
       ▼
 Intraday peak (+453 USD theoretical)
       │
       ▼
   NO EXIT / weak exit ───────────────────────► Profit evaporation (-33 USD)
       │
       ▼
   STOP LOSS
       │
       ▼
 Immediate re-BUY (high score) ──────────────► BUY→STOP→BUY churn
       │
       ▼
 Second STOP ───────────────────────────────► Compounding loss
```

Three independent failure hypotheses — each needs its own validator:

| Hypothesis | Module | Primary question |
|------------|--------|------------------|
| H1 — Exit / profit protection | X.PROTECT-2 | Would partial sell or trailing have retained more intraday gain? |
| H2 — Re-entry after STOP | X.COOLDOWN-1 | Does immediate re-BUY after STOP destroy expectancy? |
| H3 — Decision sequencing | X.REPLAY-1 | Which single decision cost the most; entry vs exit vs re-entry? |

No live change until all three produce converging evidence and X.KNOWLEDGE-1B promotes findings with sufficient confidence.

---

## A. X.PROTECT-2 — Historical Profit Protection Validator

### Purpose

Backtest shadow protection strategies **on accumulated history**, not just the current snapshot. X.PROTECT-1 evaluates *today’s* open book; X.PROTECT-2 answers: *over N days, which rule would have improved outcomes and with what trade-offs?*

### Inputs (read-only)

| Source | Path | Role |
|--------|------|------|
| Fade history (SSOT for intraday observations) | `runtime_outputs/tae_intraday_fade_history.csv` | Per-position rows with shadow PnL columns |
| Daily summaries | `runtime_outputs/tae_intraday_fade_daily_summary.json` | Portfolio-level daily totals |
| Current shadow signals | `tae_profit_protection_shadow.json` | Rule definitions / latest snapshot for consistency check |
| Discovery patterns | `tae_intraday_discovery_engine.json` | Ticker-level best shadow strategy hints |
| Knowledge base | `tae_knowledge_base.json` | Consolidated recommendations (no rewrite) |
| Portfolio (FIFO reference) | `portfolio.csv` | Validate share counts; **read-only** |

**Reuse from existing code (import, do not duplicate):**

- `fifo_open_positions()` from `tae_intraday_fade_intelligence.py`
- Shadow column names / strategy keys from `tae_intraday_fade_history.py` (`shadow_sell_20`, `shadow_sell_30`, `shadow_trailing_1`, `shadow_trailing_1_5`)
- Rule thresholds from `evaluate_protection_signal()` in `tae_profit_protection_shadow.py` (reference implementation)

### Counterfactual strategies compared

| Strategy ID | Description | Source column / logic |
|-------------|-------------|----------------------|
| `HOLD_ACTUAL` | Baseline — current unrealized at observation time | `current` × shares vs avg |
| `SELL_20_AT_FADE` | 20% partial at intraday high, rest at current | `shadow_sell_20` |
| `SELL_30_AT_FADE` | 30% partial at intraday high, rest at current | `shadow_sell_30` |
| `TRAILING_1PCT` | 1% trailing stop from high | `shadow_trailing_1` |
| `TRAILING_1_5PCT` | 1.5% trailing stop from high | `shadow_trailing_1_5` |
| `NO_ACTION` | Explicit null strategy for delta vs HOLD | 0 shadow adjustment |

All strategies already computed at observation time in fade history — X.PROTECT-2 **aggregates and validates**, it does not re-fetch market data unless a row lacks shadow columns (then mark `DATA_GAP`, skip row).

### Core metrics (per strategy, per ticker, portfolio)

| Metric | Definition |
|--------|------------|
| `total_pnl_usd` | Sum of strategy PnL across observations |
| `delta_vs_hold_usd` | Strategy total − HOLD total |
| `win_rate` | Observations where strategy ≥ HOLD |
| `observation_count` | Rows used (exclude `DATA_UNAVAILABLE`) |
| `avg_missed_opportunity_usd` | Mean `missed_opportunity_usd` where strategy underperforms HOLD |
| `drawdown_reduction_usd` | HOLD drawdown − strategy drawdown (from high) |
| `early_cut_rate` | Fraction where strategy < HOLD but position later would have recovered (requires multi-observation same ticker/day) |
| `confidence_tier` | LOW (<30 obs), MEDIUM (30–99), HIGH (≥100) — reuse X.PROTECT-1 tiers |

### Outputs (future)

| File | Content |
|------|---------|
| `tae_profit_protection_validation.json` | Structured validation report |
| `tae_profit_protection_validation.md` | Human-readable summary |

**JSON schema (top-level):**

```json
{
  "schema": "tae_profit_protection_validation",
  "generated_at": "ISO8601",
  "mode": "SHADOW_ONLY",
  "dataset": {
    "history_rows": 0,
    "date_range": ["YYYY-MM-DD", "YYYY-MM-DD"],
    "tickers": 0,
    "data_gaps": 0
  },
  "portfolio_summary": {
    "best_strategy": "TRAILING_1PCT",
    "best_delta_vs_hold_usd": 0.0,
    "hold_total_usd": 0.0,
    "strategies": { }
  },
  "ticker_breakdown": [ ],
  "tradeoffs": {
    "early_cut_winners_count": 0,
    "early_cut_cost_usd": 0.0,
    "protection_gain_usd": 0.0,
    "net_advisory_value_usd": 0.0
  },
  "advisory_readiness": {
    "sufficient_for_advisory": false,
    "reason": "INSUFFICIENT_OBSERVATIONS | MIXED_TICKER_RESULTS | ...",
    "min_observations_required": 30
  },
  "evidence_for_knowledge_base": [ ]
}
```

### Questions answered

1. **Which strategy protected the most profit?** — Rank by `delta_vs_hold_usd` at portfolio level; secondary sort by `early_cut_rate` ascending.
2. **On which tickers?** — `ticker_breakdown[]` with per-strategy deltas (MU, PM, LLY expected high fade tickers).
3. **How often?** — `observation_count`, `win_rate` per strategy.
4. **Drawdown reduced?** — `drawdown_reduction_usd` aggregated from `drawdown_from_high_pct` × notional.
5. **Risk of cutting winners too early?** — `early_cut_rate` + `early_cut_cost_usd` vs `protection_gain_usd`.
6. **Sufficient for advisory?** — Gate: ≥30 portfolio-level observations, best strategy wins on ≥60% of ticker-days, `net_advisory_value_usd` > 0, confidence not LOW.

### Overlap / boundaries

| Module | Overlap with X.PROTECT-2 | Resolution |
|--------|--------------------------|------------|
| X.PROTECT-1 | Same strategy names | PROTECT-1 = live snapshot; PROTECT-2 = historical validator. PROTECT-2 imports rule defs, does not re-emit live signals. |
| X.INTRADAY discovery | Both rank shadow strategies | Discovery finds patterns; PROTECT-2 validates PnL impact. Discovery feeds context, not ground truth. |
| X.KNOWLEDGE-1A | Both emit recommendations | Knowledge **consumes** PROTECT-2 `evidence_for_knowledge_base[]`; PROTECT-2 does not write to `tae_knowledge_base.json`. |

---

## B. X.COOLDOWN-1 — Stop Re-entry Cooldown Shadow

### Purpose

Quantify damage from **immediate re-entry after STOP** — the MU / PM / LLY / MC.PA pattern where score stays high and bot re-BUYs within minutes.

### Inputs (read-only)

| Source | Path | Role |
|--------|------|------|
| Portfolio ledger | `portfolio.csv` | BUY / SELL / STOP events with timestamps |
| Live signals | `live_signals.csv` | Score at signal time (STRONG BUY 100, etc.) |
| Accounting snapshot | `tae_accounting_snapshot.json` (via `research_core.accounting`) | Realized PnL per trade, STOP attribution |
| Intraday history | `runtime_outputs/tae_intraday_fade_history.csv` | Context on same-day fade (optional enrichment) |

**Reuse:**

- `build_accounting_snapshot()` from `research_core.accounting.accounting_snapshot`
- Event parsing patterns from `tae_accounting_consistency_check.py` (reference, do not duplicate ledger logic inline)

### Sequence detection algorithm

For each `(ticker, trading_date)`:

1. Sort portfolio events by timestamp.
2. Find `STOP_LOSS` (or SELL with stop reason if encoded).
3. Find next `BUY` on same ticker same day.
4. If `Δt ≤ 5 minutes` → flag as **rapid re-entry**.
5. Attach `score_at_rebuy` from nearest `live_signals.csv` row (same ticker, timestamp ≤ rebuy + 1 min).
6. Classify outcome of re-entry leg:
   - `SECOND_STOP` — next exit is STOP within same day
   - `RECOVERY` — closed green or still open green at EOD observation
   - `OPEN` — still holding at analysis time

### Cooldown simulations (shadow gates)

| Policy | Rule |
|--------|------|
| `COOLDOWN_15M` | Block re-BUY until 15 min after STOP |
| `COOLDOWN_30M` | Block re-BUY until 30 min after STOP |
| `COOLDOWN_60M` | Block re-BUY until 60 min after STOP |
| `COOLDOWN_NEXT_SESSION` | Block re-BUY until next market session open |
| `COOLDOWN_NEW_CONFIRMATION` | Block until score drops below threshold then rises again, or new signal type (design: score drop ≥20 pts or 2 consecutive non-BUY scans) |

For each policy: **counterfactual PnL** = actual PnL − PnL of suppressed re-entry legs (the BUY→STOP→BUY legs that would not have happened).

### Outputs (future)

| File | Content |
|------|---------|
| `tae_stop_reentry_cooldown_audit.json` | Audit results |
| `tae_stop_reentry_cooldown_audit.md` | Summary |

**Key JSON sections:**

```json
{
  "schema": "tae_stop_reentry_cooldown_audit",
  "rapid_reentry_sequences": [
    {
      "ticker": "MU",
      "date": "YYYY-MM-DD",
      "stop_time": "...",
      "rebuy_time": "...",
      "minutes_after_stop": 2,
      "score_at_rebuy": 100,
      "outcome": "SECOND_STOP",
      "leg_pnl_usd": -45.0
    }
  ],
  "summary": {
    "total_rapid_reentries": 0,
    "profitable_reentries": 0,
    "second_stop_count": 0,
    "pnl_of_rapid_legs_usd": 0.0
  },
  "cooldown_simulation": {
    "COOLDOWN_30M": { "prevented_trades": 0, "saved_pnl_usd": 0.0, "missed_gains_usd": 0.0 }
  },
  "recommended_shadow_cooldown": null,
  "advisory_readiness": { "sufficient": false }
}
```

### Questions answered

1. **How many rapid re-entries?** — `total_rapid_reentries`
2. **How many profitable?** — `profitable_reentries` / win rate
3. **How many led to second STOP?** — `second_stop_count`
4. **PnL saved by cooldown?** — `saved_pnl_usd` per policy minus `missed_gains_usd`
5. **Optimal cooldown?** — Policy with max `saved_pnl_usd − missed_gains_usd` subject to not blocking >X% of profitable re-entries (default X=20%)

### Overlap / boundaries

| Module | Overlap | Resolution |
|--------|---------|------------|
| X.REPLAY-1 | Both analyze BUY/STOP sequences | COOLDOWN-1 is specialized on re-entry timing; REPLAY-1 calls COOLDOWN findings as one counterfactual branch. |
| X.PROTECT-2 | Both touch PnL | PROTECT-2 = exit strategy; COOLDOWN-1 = entry gating. Separate outputs. |
| Score engine (live) | High score after STOP | COOLDOWN-1 **reports** score-at-rebuy; does not modify scoring. X.KNOWLEDGE-1B handles confidence decay later. |

---

## C. X.REPLAY-1 — Decision Replay Engine

### Purpose

Reconstruct **each decision event** on a trading day and score counterfactual alternatives — the integrator that answers *where* in the decision chain value was lost.

### Inputs (read-only)

| Source | Path |
|--------|------|
| `portfolio.csv` | Canonical event stream |
| `live_signals.csv` | Scores / signal types at decision time |
| `tae_accounting_snapshot.json` | Realized PnL attribution |
| `runtime_outputs/tae_intraday_fade_history.csv` | Intraday path (high, fade) |
| `tae_profit_protection_validation.json` | Best exit strategy (from X.PROTECT-2) |
| `tae_stop_reentry_cooldown_audit.json` | Best cooldown policy (from X.COOLDOWN-1) |

### Event model

Each row in replay = one **DecisionEvent**:

```json
{
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "ticker": "MU",
  "event_type": "BUY | SELL | STOP | TAKE_PROFIT | HOLD",
  "actual_pnl_usd": 0.0,
  "score_at_event": 100,
  "counterfactuals": [
    { "action": "SKIP_BUY", "estimated_pnl_usd": 0.0, "delta_usd": 0.0 },
    { "action": "DELAY_BUY_15M", "estimated_pnl_usd": 0.0, "delta_usd": 0.0 },
    { "action": "NO_REENTRY_AFTER_STOP", "estimated_pnl_usd": 0.0, "delta_usd": 0.0 },
    { "action": "APPLY_TRAILING_1PCT", "estimated_pnl_usd": 0.0, "delta_usd": 0.0 },
    { "action": "SELL_20_PCT", "estimated_pnl_usd": 0.0, "delta_usd": 0.0 },
    { "action": "SELL_30_PCT", "estimated_pnl_usd": 0.0, "delta_usd": 0.0 },
    { "action": "HOLD_TO_CLOSE", "estimated_pnl_usd": 0.0, "delta_usd": 0.0 }
  ],
  "best_counterfactual": "APPLY_TRAILING_1PCT",
  "failure_mode": "EXIT | REENTRY | ENTRY | NONE",
  "cost_usd": 0.0
}
```

### Counterfactual estimation rules

| Alternative | Estimation source |
|-------------|-------------------|
| Skip BUY | 0 (avoid loss/gain of leg) |
| Delay BUY 15M | Use intraday price 15m later from fade history or yfinance shadow fetch (SHADOW fetch OK) |
| No re-entry after STOP | COOLDOWN-1 saved PnL for that sequence |
| Trailing / partial sell | PROTECT-2 shadow columns for matching observation |
| Hold to close | EOD price from fade history row |

`cost_usd = actual_pnl − best_counterfactual_pnl` (positive = decision cost money).

### Outputs (future)

| File | Content |
|------|---------|
| `tae_decision_replay.json` | Full event replay |
| `tae_decision_replay.md` | Daily / weekly narrative |

**Aggregate sections:**

- `top_cost_decisions[]` — sorted by `cost_usd` descending
- `failure_mode_breakdown` — `{ "EXIT": 320, "REENTRY": 180, "ENTRY": 45 }`
- `lessons_for_knowledge_base[]` — structured evidence packets for X.KNOWLEDGE-1B

### Questions answered

1. **Most expensive decision?** — `top_cost_decisions[0]`
2. **Best alternative?** — `best_counterfactual` per event
3. **Dominant failure mode?** — `failure_mode_breakdown` majority
4. **Knowledge lessons?** — e.g. `"MU 2026-06-30: EXIT failure; trailing_1 would have +$42 vs actual -$18"`

### Overlap / boundaries

| Module | Role |
|--------|------|
| X.PROTECT-2 | Supplies exit counterfactual numbers |
| X.COOLDOWN-1 | Supplies re-entry counterfactual numbers |
| X.REPLAY-1 | **Orchestrator** — does not recompute shadow sims; imports upstream validation outputs |

**Risk:** REPLAY must not become a fourth shadow simulator. It **composes** PROTECT-2 + COOLDOWN-1 + ledger facts.

---

## D. Recommended build order

```
1. X.PROTECT-2   Historical Profit Protection Validator
       │
       ▼
2. X.COOLDOWN-1  Stop Re-entry Cooldown Shadow
       │
       ▼
3. X.REPLAY-1    Decision Replay Engine
       │
       ▼
4. X.KNOWLEDGE-1B  Confidence Evolution
       │
       ▼
5. X.PROTECT-3   Advisory (dashboard / committee hints)
       └── only if steps 1–4 converge with HIGH confidence
```

### Why this order

| Step | Rationale |
|------|-----------|
| **1. X.PROTECT-2 first** | Shadow PnL columns **already exist** in `tae_intraday_fade_history.csv`. Lowest implementation cost, highest immediate value. Directly addresses the +486 USD evaporation hypothesis with data on hand. |
| **2. X.COOLDOWN-1 second** | Requires clean event parsing from `portfolio.csv` + `live_signals.csv` — slightly more complex, but independent of PROTECT-2. Addresses the BUY→STOP→BUY churn with clear counterfactual. |
| **3. X.REPLAY-1 third** | **Depends on outputs** of PROTECT-2 and COOLDOWN-1 for counterfactual numbers. Without them, replay would re-derive everything (duplication risk). |
| **4. X.KNOWLEDGE-1B fourth** | Consolidation layer exists (1A). Evolution module promotes findings from validation/replay **only when** observation thresholds met — prevents premature score or exit changes. |
| **5. X.PROTECT-3 last** | Advisory UI / committee hints. **Forbidden** until validation shows consistent edge; otherwise dashboard noise and false confidence. |

---

## E. Strict rules (all modules)

| Rule | Enforcement |
|------|-------------|
| SHADOW_ONLY | All outputs tagged; no broker calls |
| PAPER_ONLY | No live order generation |
| NO_BROKER | No IB / execution adapter imports |
| No `live_bot.py` changes | CI grep / module boundary |
| No writes to `portfolio.csv` | Read-only pandas load |
| No writes to `live_signals.csv` | Read-only |
| No real BUY/SELL/STOP | Output actions limited to `TEST_*`, `OBSERVE`, `SHADOW_*` |
| Writes only JSON/MD reports | Under project root or `runtime_outputs/` |
| Knowledge feed | Emit `evidence_for_knowledge_base[]` arrays; X.KNOWLEDGE-1B consumes — **no direct KB writes** |

---

## F. Existing modules — reuse, avoid duplication, SSOT

### Reuse (import / read)

| Module | Reuse |
|--------|-------|
| `tae_intraday_fade_intelligence.py` | `fifo_open_positions()`, shadow simulation math, classification buckets |
| `tae_intraday_fade_history.py` | CSV schema, column names, dedupe by `run_id` |
| `tae_intraday_discovery_engine.py` | Pattern types, confidence tiers, ticker learning |
| `tae_profit_protection_shadow.py` | `evaluate_protection_signal()`, strategy IDs, SHADOW_ACTIONS set |
| `tae_knowledge_base.py` | Read `tae_knowledge_base.json` only; normalization helpers if exported |
| `research_core.accounting.accounting_snapshot` | PnL attribution, event ledger |
| `tae_accounting_consistency_check.py` | Portfolio event parsing patterns (reference) |

### Do NOT duplicate

| Already exists | Do not rebuild |
|----------------|----------------|
| Intraday shadow PnL simulation | Already in fade intelligence → history CSV |
| Live snapshot protection signals | X.PROTECT-1 |
| Pattern discovery from fade history | X.INTRADAY discovery engine |
| Knowledge consolidation VIEW | X.KNOWLEDGE-1A |
| FIFO cost basis | `fifo_open_positions()` |
| Evidence registry | `tae_evidence_engine_report.json` |

### SSOT map

| Information type | SSOT | Consumers |
|------------------|------|-----------|
| Open positions / cost basis | `portfolio.csv` | All three modules (read-only) |
| Intraday observations | `runtime_outputs/tae_intraday_fade_history.csv` | PROTECT-2, REPLAY-1 |
| Shadow strategy PnL per observation | Columns in fade history CSV | PROTECT-2 (aggregate), REPLAY-1 (lookup) |
| Live protection snapshot | `tae_profit_protection_shadow.json` | PROTECT-2 (rule consistency) |
| Pattern / ticker learning | `tae_intraday_discovery_engine.json` | PROTECT-2, KNOWLEDGE-1B |
| Consolidated knowledge VIEW | `tae_knowledge_base.json` | All modules read; only KNOWLEDGE-1B writes |
| Realized / corrected PnL | `tae_accounting_snapshot.json` | COOLDOWN-1, REPLAY-1 |
| Signal scores | `live_signals.csv` | COOLDOWN-1, REPLAY-1 |
| Validation results (future) | `tae_profit_protection_validation.json` | REPLAY-1, KNOWLEDGE-1B |
| Cooldown audit (future) | `tae_stop_reentry_cooldown_audit.json` | REPLAY-1, KNOWLEDGE-1B |

### Overlap risks

| Risk | Mitigation |
|------|------------|
| PROTECT-1 vs PROTECT-2 both rank strategies | PROTECT-1 = point-in-time; PROTECT-2 = historical. Single strategy enum shared via constants module or import from PROTECT-1. |
| Discovery vs PROTECT-2 both say "best shadow" | Discovery = pattern frequency; PROTECT-2 = PnL validation. PROTECT-2 outcome overrides discovery for advisory. |
| REPLAY re-simulates shadows | REPLAY imports PROTECT-2/COOLDOWN JSON; never calls yfinance unless DELAY_BUY needs price (isolated helper). |
| KNOWLEDGE-1A vs 1B | 1A = materialized VIEW rebuild; 1B = confidence evolution + promotion gates only. |

---

## G. Test strategy (future)

### Shared fixtures (`tests/fixtures/performance/`)

| Fixture | Purpose |
|---------|---------|
| `fade_history_evaporation.csv` | Rows: high +5%, current -1%, large `missed_opportunity_usd` |
| `fade_history_trailing_winner.csv` | Trailing captures most of high; HOLD underperforms |
| `fade_history_early_cut.csv` | Trailing exits early; later row shows recovery — tests `early_cut_rate` |
| `portfolio_buy_stop_buy.json` | MU-style sequence within 3 minutes |
| `portfolio_single_stop.json` | Control — no re-entry |
| `live_signals_high_after_stop.csv` | STOP then STRONG BUY 100 |
| `empty_history.csv` | Missing data path |
| `duplicate_run_ids.csv` | Dedupe correctness |

### X.PROTECT-2 tests

- Aggregates shadow columns correctly vs manual sum
- HOLD baseline matches `current` PnL formula
- Best strategy selection with clear winner
- Tie-breaking: prefer lower `early_cut_rate`
- `DATA_UNAVAILABLE` rows excluded
- Empty CSV → graceful report, `advisory_readiness.sufficient = false`
- FIFO: share count matches portfolio for sample ticker

### X.COOLDOWN-1 tests

- Detects rapid re-entry within 5 min
- Ignores re-entry next day
- `SECOND_STOP` classification correct
- Cooldown 30M prevents fictional BUY → saved PnL matches fixture
- `COOLDOWN_NEW_CONFIRMATION` respects score drop logic
- Missing `live_signals.csv` → WARN, score null
- Duplicate portfolio rows → dedupe by timestamp+ticker+action

### X.REPLAY-1 tests

- Composes PROTECT-2 + COOLDOWN JSON without recomputing
- `failure_mode=EXIT` when trailing beats actual on STOP event
- `failure_mode=REENTRY` when cooldown would have blocked losing rebuy
- `top_cost_decisions` ordering
- `lessons_for_knowledge_base` schema valid for KNOWLEDGE-1B ingest
- Missing upstream JSON → degrade gracefully, mark incomplete counterfactuals

### FIFO correctness (all modules)

- Use `fifo_open_positions()` — never custom cost basis
- Test: multiple BUY same ticker, partial SELL, verify open shares
- Test: STOP clears lot; re-BUY starts new lot

---

## H. Final verdict

### BUILD / DO NOT BUILD

**BUILD** — the problem is diagnosed, data pipeline exists, and shadow columns are already persisted. Risk of **not building** is continued profit evaporation with no validated counterfactual. Risk of **building** is low: all modules are read-only reports.

### First module to construct

**X.PROTECT-2 — Historical Profit Protection Validator**

Reason: uses existing `tae_intraday_fade_history.csv` shadow columns immediately; answers the largest observed gap (+486 USD missed); 11 tests already prove PROTECT-1 rules — PROTECT-2 extends to N-day validation.

### Conditions before any real advisory (X.PROTECT-3 or live change)

| Gate | Threshold |
|------|-----------|
| G1 — Observations | ≥ **30** valid fade history rows (portfolio-level) |
| G2 — Strategy dominance | Best shadow strategy wins ≥ **60%** of ticker-day observations |
| G3 — Net value | `net_advisory_value_usd` > 0 after early-cut penalty |
| G4 — Cooldown evidence | COOLDOWN-1 shows ≥ **3** rapid re-entries with net saved PnL > 0 at recommended policy |
| G5 — Replay convergence | REPLAY-1 `failure_mode_breakdown` top mode aligns with PROTECT-2 or COOLDOWN-1 finding |
| G6 — Knowledge promotion | X.KNOWLEDGE-1B promotes finding to `LEARNING` or `CONFIRMED` — not `EXPERIMENTAL` |
| G7 — Human review | Explicit sign-off; no auto-apply to `live_bot.py` |
| G8 — Mode unchanged until G1–G7 pass | PAPER_ONLY / NO_BROKER / SHADOW_ONLY |

**Do NOT build X.PROTECT-3 advisory** until G1–G6 pass on rolling 30-day window.

### Expected outcome after full stack

If hypotheses confirm:

- **Primary lever:** trailing 1% or partial 20–30% on high-fade tickers (PROTECT-2)
- **Secondary lever:** 30–60 min cooldown after STOP on repeat offenders (COOLDOWN-1)
- **Not primary:** entry scoring changes — unless REPLAY-1 shows ENTRY dominates (unlikely given current audit)

Score persistence after STOP (STRONG BUY 100) is a **X.KNOWLEDGE-1B** concern — confidence decay after STOP — not a live_bot change in this phase.

---

## Appendix — confirmed untouched by this design

| Asset | Status |
|-------|--------|
| `live_bot.py` | Not modified |
| BUY / SELL / Risk / Broker / Trailing logic | Not modified |
| Market Data Layer | Not modified |
| Strategies / scoring engine | Not modified |
| `portfolio.csv` / `live_signals.csv` | Read-only if present |
| Git commit | None |

---

*TAE PERFORMANCE-1 — architecture design only. Research path to profit growth without live execution risk.*
