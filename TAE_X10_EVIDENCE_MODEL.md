# TAE X.10 Evidence Model

**Date:** 2026-07-05  
**Mode:** READ ONLY — methodology only; no implementation, no code, no commit  
**Authority:** `TAE_STRATEGIC_GAP_AUDIT.md`, `PROJECT_BOOK.md` §12, `TAE_DEVELOPMENT_PROTOCOL.md`, `TAE_IMPLEMENTATION_ROADMAP.md` Phase 3-F, repository state at X.Decision checkpoint (`50ebc0b`)

---

## Purpose

Define how TAE should **objectively measure** whether a BUY blocked by the X.8 live gate (`RISK_ADVISORY` → `BUY_BLOCKED_BY_TAE`) was beneficial, harmful, or inconclusive — before any X.10 build work begins.

This document is the **evidence methodology SSOT** for X.10. It does not specify modules, APIs, or file layouts beyond naming existing artifact roles.

---

## Repository baseline (pre-build audit)

| Metric | Value (2026-07-05 ledger) |
|--------|----------------------------|
| Total shadow events | 2,544 |
| `BUY_BLOCKED_BY_TAE` | **0** |
| `BUY_ALLOWED` | 25 |
| `BUY_SKIPPED_OTHER_REASON` | 2,519 (mostly `MARKET_SESSION_FILTER`, `MAX_POSITIONS`) |

**Implication:** X.10 methodology must be correct when `BUY_BLOCKED_BY_TAE` is sparse or zero, but **must not** attribute outcomes to X.8 for non-TAE skips. Aggregate gate statistics remain `PENDING_NEXT_PHASE` until at least one resolved blocked cohort exists.

---

## Methodology overview

X.10 answers one question per eligible event:

> *If live_bot had executed the blocked BUY at the logged evaluation, what PnL would have resulted over defined forward windows — and does that imply the block helped, hurt, or did not matter?*

This is a **counterfactual paper simulation**, not realized PnL. The blocked trade never happened; outcome is inferred from forward prices under **live_bot-equivalent exit rules**.

**In scope:** `event_type == BUY_BLOCKED_BY_TAE` only.  
**Out of scope for X.8 attribution:** `BUY_SKIPPED_OTHER_REASON` (session filter, max positions, sub-min trade, etc.).  
**Control cohort (optional):** `BUY_ALLOWED` — realized or simulated path for calibration, not mixed into block WIN/LOSS rates.

---

## Architecture (logical)

```
tae_shadow_validation_events.csv
        │
        │ filter: BUY_BLOCKED_BY_TAE
        ▼
┌───────────────────────────────────────┐
│ Event eligibility & sizing reconstruction │
│  - entry anchor (event price / session) │
│  - intended notional (reconstruct if missing) │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ Forward price path (read-only marks)      │
│  live_signals.csv → portfolio.csv →      │
│  external daily marks (fallback only)     │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ Counterfactual path simulator             │
│  STOP -3% · TAKE PROFIT +5% (live_bot)   │
│  per-window MAE / MFE / exit reason       │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ Outcome record + WIN/LOSS/NEUTRAL         │
│  intervention_value_usd = -cf_pnl_usd     │
└───────────────────────────────────────┘
        │
        ├──► tae_shadow_validation_outcomes.json (future artifact)
        ├──► tae_shadow_validation_summary.json (outcome_tracking_status)
        ├──► counterfactual / unified runtime Outcome_Memory fields
        └──► confidence_evolution evidence feed (aggregate only)
```

**Constraints (mandatory):** `ANALYSIS_ONLY` · `PAPER_ONLY` · `NO_BROKER` · `NO_EXECUTION`. No writes to `portfolio.csv`, `live_signals.csv`, or `live_bot.py`.

---

## Data flow

| Stage | Input SSOT | Output concept |
|-------|------------|----------------|
| 1. Event selection | `tae_shadow_validation_events.csv` | Eligible blocked events + metadata |
| 2. Entry anchor | Event `timestamp`, `ticker`, `price` | Counterfactual entry price + session |
| 3. Size | Event `intended_trade_usd` / `shares` **or** reconstructed from same-cycle context | Simulated notional and share count |
| 4. Forward marks | `live_signals.csv`, `portfolio.csv`, optional price fallback | Daily/intraday price series per ticker |
| 5. Path simulation | `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT` from live bot policy | Per-window PnL, MAE, MFE, exit type |
| 6. Benchmark overlay | SPY (or `MARKET_REGIME_TICKER`) same window | Relative return (secondary) |
| 7. Verdict | Methodology rules below | WIN / LOSS / NEUTRAL + status |
| 8. Aggregation | Weighted rollup by `primary_blocker` | Gate effectiveness metrics |

---

## Attribution model

### Execution attribution (single live cause)

Only **one module** causes X.8 blocks today:

| Layer | Role in X.10 |
|-------|----------------|
| **`live_advisory_runtime` + X.8 gate** | **Sole execution blocker** — `RISK_ADVISORY` → `BUY_BLOCKED_BY_TAE` |
| `live_advisory_bridge` | Source of `advisory_blockers[]`, `advisory_reasons[]`, `advisory_confidence` at block time |
| Decision governor VIEW | **No execution credit** — informational enrichment only (X.DECISION-2B) |
| Cooldown / protection / knowledge shadow stack | **No execution credit** unless a finding appears in `advisory_blockers[]` at block time |

### Diagnostic attribution (why RISK fired)

When `advisory_blockers[]` contains multiple items, assign:

1. **`primary_blocker`** — first blocker in bridge precedence order that **alone** would trigger `RISK_ADVISORY`:
   - Invalid TAE index reports (`invalid_reports > 0`)
   - Elevated blocking warning count (≥ 2)
   - Trading blockers count (≥ 3 non-informational blockers)
   - Open book stress (≥ 2 positions below −3% PnL, or outlier-driven historical contradiction)
   - Quick health not ready
   - Strategic performance audit anomaly flag

2. **`contributing_blockers`** — remaining entries in `advisory_blockers[]` at event time.

3. **`shadow_context_tags`** — parsed from `advisory_reasons[]` prefixes (`[GOVERNOR_*]`, `[REPLAY_*]`, `[CONFIDENCE_*]`, etc.) — **context only**, not causal credit for WIN/LOSS.

**Governor / Cooldown / Knowledge / Protection:** receive **diagnostic tags** if referenced in reasons or blockers; they do **not** receive independent execution credit while X.8 remains the only live block path.

---

## Statistical assumptions

1. **Counterfactual independence:** Forward prices for the ticker are unaffected by the block (paper mode; no market impact).
2. **Policy fidelity:** Simulated exits use the same stop (−3%) and take-profit (+5%) thresholds as `live_bot.py` at evaluation time (not trailing logic unless explicitly in scope later).
3. **Entry price:** Signal price at event timestamp is the counterfactual fill unless session rules require next tradable open (see edge cases).
4. **Sizing:** Counterfactual position size matches what live_bot would have allocated at that cycle (see partial-fill section).
5. **Minimum sample for gate conclusions:** No change to X.8 policy from aggregate stats until **≥ 30 resolved** `BUY_BLOCKED_BY_TAE` outcomes per `primary_blocker` class (or ≥ 30 total if classes are sparse).
6. **Significance for learning promotion:** Aggregate blocker effectiveness requires bootstrap 95% CI on mean `intervention_value_usd` excluding zero, or two-proportion test on WIN rate vs 50% at α = 0.05.
7. **Non-stationarity:** Events across different advisory regimes (e.g. `SELL_ADVISORY` vs `RISK_ADVISORY` background) are tagged but not assumed exchangeable without stratification.

---

## Question 1 — What constitutes an "Outcome" for a blocked BUY?

An **Outcome** is a **resolved counterfactual evaluation** for one `BUY_BLOCKED_BY_TAE` event, comprising:

| Field group | Definition |
|-------------|------------|
| **Identity** | Event key: `timestamp` + `ticker` + `live_bot_cycle_id` |
| **Counterfactual entry** | Simulated BUY at anchor price with reconstructed notional |
| **Forward path** | Price series from entry through each observation window |
| **Simulated exit** | First touch of stop (−3%), take profit (+5%), or mark-to-market at window end |
| **Core metrics** | `counterfactual_pnl_usd`, `counterfactual_pnl_pct`, `mae_pct`, `mfe_pct`, `exit_reason` |
| **Intervention value** | `intervention_value_usd = -counterfactual_pnl_usd` (positive ⇒ block helped) |
| **Relative benchmark** | SPY (or regime ticker) return over same window |
| **Verdict** | `WIN` / `LOSS` / `NEUTRAL` |
| **Resolution status** | `RESOLVED` / `OUTCOME_PENDING` / `SIGNAL_EXPIRED` / `OUTCOME_UNMEASURABLE` |
| **Attribution** | `primary_blocker`, `contributing_blockers[]`, `shadow_context_tags[]` |

An outcome is **not** realized portfolio PnL (the trade did not occur). It is **evidence** for whether the X.8 intervention was ex-post justified.

---

## Question 2 — Observation windows

### Recommended windows

| Window | Type | Role |
|--------|------|------|
| **1 trading day (1D)** | Primary diagnostic | Captures immediate adverse moves after STRONG BUY signals; aligns with bot’s short-cycle evaluation |
| **5 trading days (5D)** | **Primary decision window** | Matches typical hold-to-stop/take-profit horizon for paper bot; balances noise vs signal |
| **10 trading days (10D)** | **Primary aggregate window** | Stable enough for rollup statistics; referenced in roadmap “accumulate ≥ N events” spirit |
| **20 trading days (20D)** | Secondary | Detects missed trends when stop not hit; useful for false-block analysis |

### Not recommended as primary (initial X.10)

| Window | Why defer |
|--------|-----------|
| **3D** | Redundant with 1D + 5D; adds reporting surface without new decision insight |
| **30D** | Confounds with new signal cycles, watchlist churn, and regime shifts; violates local counterfactual interpretability |

**Rule:** All windows are measured in **trading days** on the **ticker’s exchange calendar**, not calendar days.

Each event produces **one outcome record per window**. Aggregate gate metrics use **10D** as the headline window; **5D** for tactical review; **1D** for crash-avoidance detection.

---

## Question 3 — Benchmark

### Primary benchmark (counterfactual PnL)

**Entry anchor: event `price` at block timestamp** — the same price `live_bot.py` used when evaluating the BUY.

Rationale: The bot does not use next-open fills; it uses the signal row price during an open session evaluation. Matching live behavior avoids optimistic/pessimistic fill bias.

**Session exception:** If the event timestamp falls outside the ticker’s regular session (data anomaly only — live_bot normally blocks via `MARKET_SESSION_FILTER` before TAE block), anchor shifts to **next tradable session open** for that market. Tag `entry_anchor: NEXT_OPEN`.

### Secondary benchmarks (context, not WIN/LOSS driver)

| Benchmark | Use |
|-----------|-----|
| **SPY same-window return** | Regime context; `relative_alpha = counterfactual_pnl_pct - spy_return_pct` |
| **Next close** | Diagnostic only — compare signal price vs same-day close slippage |
| **ATR-adjusted move** | Optional flag for volatile names (MAE > 1.5× ATR(14)) — does not override USD verdict |

### Not primary

| Benchmark | Why not |
|-----------|---------|
| **Sector-relative** | Sector mapping incomplete across watchlist (US, LSE, XETRA); use as future enrichment only |
| **Historical robust median** | Strategy-level, not event-level counterfactual |

---

## Question 4 — How should success be measured?

Success is **multi-metric** but **single headline** for gate decisions:

### Headline metric

**`intervention_value_usd`** at the primary window (10D):

```
intervention_value_usd = -counterfactual_pnl_usd
```

Positive intervention value ⇒ the block avoided loss or forgone gain that would have been negative.

### Supporting metrics (required on every outcome record)

| Metric | Purpose |
|--------|---------|
| **Absolute return (`counterfactual_pnl_pct`)** | Raw counterfactual performance |
| **Max adverse excursion (MAE)** | Worst drawdown from entry before window end or stop |
| **Max favorable excursion (MFE)** | Best unrealized gain before exit |
| **Drawdown avoided** | For WIN cases: `max(0, -counterfactual_pnl_usd)` when counterfactual would have lost |
| **Missed gain** | For LOSS cases: `max(0, counterfactual_pnl_usd)` when counterfactual would have won |
| **SPY-relative alpha** | Secondary quality check |
| **Stop / take-profit hit flags** | Explain exit path |

### Not headline for X.10

| Metric | Role |
|--------|------|
| **Risk-adjusted return (Sharpe)** | Insufficient per-event history; use only in aggregate studies with n ≥ 30 |
| **Volatility alone** | Context tag only — high vol does not imply block was correct |

**Gate success (aggregate):** Mean `intervention_value_usd` > 0 with CI excluding zero, and WIN rate > LOSS rate on 10D window — still **report-only**; no auto-tightening of X.8 without architect approval.

---

## Question 5 — WIN / LOSS / NEUTRAL (exact criteria)

Define **epsilon** (noise floor) per event:

```
epsilon_usd = max(5.00, 0.0015 × intended_notional_usd)
```

All comparisons use **`intervention_value_usd`** at the **10D window** unless status prevents 10D resolution (then 5D, then 1D).

### WIN (block beneficial)

Any of:

1. `intervention_value_usd > epsilon_usd`  
   *(counterfactual PnL negative — block avoided loss)*

2. **Stop-equivalent avoidance:** MAE ≤ −3.0% and counterfactual would have exited at stop before window end, and `intervention_value_usd ≥ 0`  
   *(block avoided a stop-loss path)*

### LOSS (block harmful)

All of:

1. `intervention_value_usd < -epsilon_usd`  
   *(counterfactual PnL positive — missed gain)*

2. Counterfactual path **does not** hit stop (−3%) before window end

3. `counterfactual_pnl_pct` at window end > +epsilon_pct where `epsilon_pct = 0.15%`

### NEUTRAL

Any of:

1. `|intervention_value_usd| ≤ epsilon_usd`

2. **Ambiguous path:** Stop and take-profit both touched within window order unresolved (same-bar ambiguity) — tag `path_ambiguous`

3. **`SIGNAL_EXPIRED`** before 5D (see Q6) — insufficient forward signal validity

4. **`OUTCOME_UNMEASURABLE`** (see Q7)

5. Reconstructed `intended_notional_usd < MIN_TRADE_USD` ($250 live_bot floor) — `NOT_EVALUABLE`

**Important:** NEUTRAL is **not** success. It excludes the event from WIN/LOSS rate numerators but keeps it in the registry.

---

## Question 6 — Expired signals

A signal **expires** at the first timestamp when any condition holds:

1. Ticker’s row in `live_signals.csv` shows `Signal != "STRONG BUY"`  
2. Score drops below `MIN_SCORE_TO_BUY` (80 in `live_bot.py`)  
3. A **real** BUY for the same ticker is recorded in `portfolio.csv` after the event (different path — block irrelevant)  
4. **10 trading days** elapsed (hard cap for counterfactual validity)

**Handling:**

| Expiry timing | Action |
|---------------|--------|
| Before 1D complete | `SIGNAL_EXPIRED` → **NEUTRAL**, window metrics computed only to expiry |
| After 1D, before 10D | Compute 1D and 5D if valid; 10D = **NEUTRAL** with `partial_window: true` |
| After real BUY in portfolio | `OUTCOME_SUPERSEDED` → exclude from gate aggregates |

Counterfactual simulation **stops** at expiry for path purposes; mark-to-market at expiry close/last mark.

---

## Question 7 — Missing market data

Priority chain for forward marks (read-only):

1. **`live_signals.csv`** — same-ticker rows after event timestamp (preferred; matches bot)  
2. **`portfolio.csv`** — price columns on subsequent bot cycles for held names  
3. **External daily OHLC fallback** — only when 1–2 absent for a trading day  

| Situation | Status | Verdict |
|-----------|--------|---------|
| Missing ≤ 1 trading day gap | Interpolate from adjacent marks | **RESOLVED** with `data_quality: DEGRADED` |
| Missing > 2 consecutive trading days | — | **OUTCOME_PENDING** (retry next batch) |
| Ticker delisted / no data after retry limit | — | **OUTCOME_UNMEASURABLE** → **NEUTRAL**, exclude from aggregates |
| Price = 0 or null at event | — | **NOT_EVALUABLE** → exclude |

Never infer prices from unrelated tickers. Never write missing data back to CSV SSOTs.

---

## Question 8 — Weekends / holidays

1. **Window unit = trading days**, not calendar days.  
2. Use **ticker exchange** from `markets/market_config` (US, LSE, XETRA, etc.) via `markets/market_hours.py`.  
3. **Weekends:** `weekday >= 5` → non-trading; do not count toward window.  
4. **Holidays:** Initial X.10 uses **weekend-only** calendar (consistent with current `market_hours.py`). Exchange holidays are a known limitation — tag `calendar: WEEKEND_ONLY` until a holiday SSOT exists.  
5. **Multi-market bot:** Each event uses **its ticker’s market** for window boundaries; do not use US calendar for `ULVR.L` or `SIE.DE`.  
6. **Batch timing:** Outcome batch runs after at least one **post-event tradable session** has completed for that ticker.

---

## Question 9 — Partial fills (simulation)

The paper bot does not model broker partial fills. X.10 simulates **live_bot-equivalent full allocation**:

1. **Preferred:** Use event `intended_trade_usd` and `shares` when present.  
2. **Reconstruction (required today):** Blocked events currently **omit** `intended_trade_usd` in the ledger. Reconstruct from same `live_bot_cycle_id`:
   - Same-cycle `BUY_ALLOWED` events share cycle sizing logic, **or**
   - Apply documented live_bot sizing: eligible STRONG BUY candidates, cash / slots, `MIN_TRADE_USD` $250, `MAX_TRADE_USD` $2500 caps, share rounding to 4 decimals.  
3. **Partial fill:** Not simulated in v1. If reconstructed size would exceed available cash or fall below `MIN_TRADE_USD`, mark **NOT_EVALUABLE**.  
4. **Slippage:** Zero in paper mode unless entry anchor uses `NEXT_OPEN` exception.

---

## Question 10 — Multiple blockers (who gets credit?)

| Actor | Execution credit | Diagnostic credit |
|-------|------------------|-------------------|
| **X.8 `RISK_ADVISORY` gate** | **100%** — only layer that blocks BUY | — |
| **`primary_blocker`** in `advisory_blockers[]` | — | **Headline for aggregate stats** |
| **Other `advisory_blockers[]`** | — | Contributing factors |
| **Governor VIEW** | **None** (not wired to block) | Tag if in reasons / enrichment |
| **Cooldown audit** | **None** unless explicit blocker text | Tag via `[REPLAY_*]` / cooldown reasons |
| **Knowledge base** | **None** unless explicit blocker text | Tag via knowledge-related reasons |
| **Profit protection shadow** | **None** unless explicit blocker text | Tag via protect/fade reasons |

**Rule:** One event → one `primary_blocker` for statistics. Multi-blocker events store **`blocker_count`** but do not split WIN/LOSS fractionally across shadow modules.

---

## Question 11 — Confidence evolution: every event or significant only?

**Two-tier learning** (consistent with `tae_confidence_evolution.py` promotion gates):

| Tier | Input | Use |
|------|-------|-----|
| **Registry (all events)** | Every **RESOLVED** outcome | Audit trail, dashboards, counterfactual context freshness |
| **Confidence / knowledge promotion** | **Statistically significant aggregates only** | n ≥ 30 per `primary_blocker`; CI excluding zero; emit `evidence_for_knowledge_base[]` — never auto-promote live |

**Do not** decay or boost live advisory confidence from a single WIN/LOSS. **Do not** write to `tae_knowledge_base.json` directly from X.10.

Individual events with `data_quality: DEGRADED` enter registry but are excluded from promotion tier until quality threshold met.

---

## Question 12 — Should evidence be weighted?

**Yes for aggregation; no for per-event WIN/LOSS label.**

Per-event verdict is unweighted (binary/ternary rules above).

**Aggregate weights** (for mean intervention value, WIN rate confidence intervals):

| Factor | Weight guidance |
|--------|-----------------|
| **`advisory_confidence`** | `0.75 + (confidence / 200)` capped to [0.75, 1.25] |
| **Intended notional** | `sqrt(intended_notional_usd / median_notional)` capped to [0.5, 2.0] |
| **Data quality** | `1.0` full marks; `0.5` degraded; `0.0` excluded |
| **Market regime** (from reasons at event time) | Optional stratification bucket — not a continuous weight in v1 |
| **Sector** | Do not weight until ticker→sector SSOT is canonical |
| **Time horizon** | Report 1D/5D/10D separately — do not blend into one weighted score |

---

## Question 13 — Existing modules that support this (reuse only)

| Module / artifact | Reuse role |
|-------------------|------------|
| `research_core/governance/shadow_validation_ledger.py` | Event schema, `BUY_BLOCKED_BY_TAE` contract |
| `tae_shadow_validation_events.csv` | Primary input SSOT |
| `tae_shadow_validation_report.py` | Summary pattern; `outcome_tracking_status` advancement |
| `tae_shadow_validation_summary.json` | Aggregate slot for block effectiveness |
| `research_core/governance/live_advisory_runtime.py` | X.8 block semantics, `RISK_ADVISORY` definition |
| `research_core/governance/live_advisory_bridge.py` | Blocker taxonomy, counterfactual reason lines |
| `research_core/counterfactual_runtime/counterfactual_context.py` | `Outcome_Memory`, shadow summary merge pattern |
| `research_core/meta_intelligence/recommendation_outcome_engine.py` | Registry + evaluation cycle pattern (not duplicate logic) |
| `research_core/meta_intelligence/recommendation_outcome_report.py` | Outcome registry persistence pattern |
| `tae_confidence_evolution.py` | Aggregate evidence ingest; promotion gate vocabulary |
| `research_core/accounting/ledger_audit.py` | Portfolio parse / FIFO reference for cross-check |
| `research_core/accounting/execution_integrity.py` | Sell/stop reason parsing if path crosses realized book |
| `tae_accounting_snapshot.json` | Portfolio-level PnL sanity check |
| `markets/market_hours.py` + `markets/market_config` | Session / exchange calendar |
| `live_signals.csv` | Forward price marks |
| `portfolio.csv` | Cycle prices, superseded-BUY detection |
| `config/settings.py` + `live_bot.py` constants | STOP −3%, TAKE +5%, min/max trade, score threshold reference |

---

## Question 14 — What MUST NOT be built

Per `PROJECT_BOOK.md` §11 and X.10 scope:

| Forbidden | Reason |
|-----------|--------|
| Second shadow BUY ledger | X.9 exists |
| Second live BUY blocker or governor live wiring | X.8 only; governor SHADOW_ONLY |
| New live↔TAE bridge | `live_advisory_bridge.py` exists |
| Duplicate decision governor / knowledge SSOT | VIEW modules exist |
| V14 `decision_registry.csv` outcome pipeline | Wrong schema and era |
| Parallel meta `RecommendationOutcomeEngine` for BUY blocks | Different domain — reuse pattern only |
| Auto-tighten X.8 from outcomes | Architect approval required |
| Writes to `portfolio.csv`, `live_signals.csv`, `live_bot.py` | Protocol violation |
| Conflating `BUY_SKIPPED_OTHER_REASON` with X.8 effectiveness | Methodology error |
| Real broker execution / partial-fill engine | PAPER_ONLY |
| Sector-relative primary SSOT | Not canonical per ticker map |
| Inline outcome computation inside `live_bot.py` | Batch read-only only |

---

## Edge cases (summary)

| Case | Handling |
|------|----------|
| Zero `BUY_BLOCKED_BY_TAE` in ledger | Methodology valid; aggregates remain `PENDING_NEXT_PHASE`; report `eligible_events: 0` |
| Block during `SELL_ADVISORY` background | Valid event — RISK can block while action is SELL_ADVISORY (observed in ledger) |
| Same ticker blocked multiple cycles | Independent outcomes per event key |
| Block then allowed later | Both events valid; block outcome uses counterfactual; allowed uses realized path (control) |
| Stale advisory file at block | Already logged in event; tag from `advisory_reasons` stale flags |
| Multi-currency tickers | PnL in USD using event price units as live_bot does |
| `BUY_ALLOWED` control cohort | Optional calibration; separate metrics from block WIN rate |

---

## Recommendation

1. **Adopt this evidence model as X.10 pre-build SSOT** — counterfactual simulation with **10D headline window**, **event price entry anchor**, **intervention_value_usd** verdict driver, and strict **`BUY_BLOCKED_BY_TAE`-only** scope.

2. **Acknowledge current data gap:** 0 blocked TAE events in the ledger today. X.10 batch should run and report `OUTCOME_PENDING` until RISK blocks occur during live cycles — without diluting metrics with session-filter skips.

3. **Reconstruct sizing** for blocked events (ledger omits `intended_trade_usd` today) using same-cycle live_bot sizing rules — document as methodology requirement, not a live_bot change.

4. **Attribute execution credit only to X.8**; use `primary_blocker` from `advisory_blockers[]` for diagnostic rollups; treat governor/cooldown/knowledge/protection as **context tags** until explicitly wired to RISK.

5. **Feed confidence evolution from aggregates only** (n ≥ 30, CI excluding zero); register every resolved outcome for audit.

6. **Advance `outcome_tracking_status`** from `PENDING_NEXT_PHASE` only when ≥ 1 resolved 10D outcome exists for the blocked cohort — even if verdict is NEUTRAL.

7. **Do not** use this evidence to auto-change live policy. Reports inform architect review only.

---

*End of TAE_X10_EVIDENCE_MODEL.md*
