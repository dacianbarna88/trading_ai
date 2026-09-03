# TAE Strategy V2 — Architecture Audit (READ-ONLY)

**Sprint:** Investment Cycle Strategy V2 — connection-point audit only  
**Generated:** 2026-07-23  
**Baseline HEAD:** `0de7812`  
**Mode:** READ-ONLY · no source changes · no commit · no V2 implementation  

---

## 1. Executive Verdict

**`READY_WITH_BLOCKERS`**

TAE already has a complete BUY→validate→execute→account and open→risk→SELL stack. Strategy V2 (tranches, company budget, controlled accumulation, thesis-driven exits) can attach **without rebuilding the ecosystem**, but only if it starts as a **feature-flagged PAPER / DPE-parallel policy** that:

- consumes existing TAE candidates and capital allocation;
- keeps Strategy V1 (`live_bot.py` + current PDE V1 behaviors) intact as benchmark;
- does **not** remove hard-risk safety;
- does **not** casually rewrite live same-ticker / full-exit semantics.

The integration point is clear. The blockers are data-model and policy gaps (no cycle/tranche schema, live forbids add-on BUY, live has no partial exit, constants fork, thesis invalidation not first-class).

---

## 2. Sursele canonice consultate

| Source | Role |
|--------|------|
| `SESSION_START.md` | Session SSOT, PAPER vs LIVE, Phase X |
| `PROJECT_BOOK.md` | Journal, closed hypotheses, governance |
| `TAE_CANONICAL_ARCHITECTURE.md` | Layer map, dual ledger |
| `TAE_CANONICAL_DECISION_FLOW.md` | PDE vs live ownership |
| `TAE_CANONICAL_RUNTIME_FLOW.md` | Runtime ownership |
| `TAE_SSOT_MATRIX.md` | Artifact owners |
| `TAE_DUAL_PHILOSOPHY_EXECUTION_ARCHITECTURE.md` | DPE parallel books / flags |
| `TAE_MASTER_STRATEGIC_EVIDENCE.md` | BUY/SELL evidence map |
| Code | `live_bot.py`, `core/trailing.py`, `hard_risk_guardian.py`, `tae_paper_decision_engine.py`, `tae_paper_execution.py`, `tae_decision_state.py`, `tae_accounting_snapshot.py`, `config/settings.py`, `core/risk.py`, DPE modules |

### Zone separation (do not conflate)

| Zone | Owner / artifacts | Notes |
|------|-------------------|-------|
| **Runtime canonic LIVE** | `live_bot.py` → `portfolio.csv`, `live_signals.csv` | Sole live fill owner |
| **Advisory** | `tae_live_advisory.json` via `live_advisory_runtime` | Blocks **new BUY only**; SELL advisory informational |
| **PAPER** | PDE → decision_state → `tae_paper_execution.py` | Isolated under `runtime_outputs/paper_*` |
| **Replay / research** | chrono replay, decision replay, stop/entry A/Bs | Shadow; must not own production |
| **Shadow / DPE** | `tae_execution_splitter.py`, `tae_dpe_*` | Dual-philosophy books; not Strategy V2 yet |
| **Legacy / demo** | `config/settings.py` V5.1, `core/risk.py`, `migration/`, `research/` | Divergent or isolated |

---

## 3. Fluxul BUY actual

### 3.1 LIVE (Strategy V1 canonical execution)

```text
watchlist.txt
  → live_bot.generate_signals()
       yfinance history → SMA50 / RSI(14) / Score / Signal
       write live_signals.csv
  → live_bot.manage_portfolio(signals, advisory)
       sizing: get_dynamic_trade_size()
       gates: session, STRONG BUY, score≥80, BULL, RISK_ADVISORY, MAX_POSITIONS
       execute: buy_position() → append BUY row → save_portfolio()
  → update_portfolio_prices() / independent risk pass
```

| Concern | Owner | Evidence |
|---------|-------|----------|
| Signal / score producer | `live_bot.generate_signals` | Close>SMA50 +40; RSI 40–65 +40; RSI 50–60 +20; ≥80 → `STRONG BUY` |
| Threshold | `MIN_SCORE_TO_BUY = 80` in `live_bot.py` | Active live |
| Market regime | `get_market_regime` (SPY vs SMA200) | BUY requires `BULL` |
| Session | `is_ticker_market_open` | Unless `ALLOW_BUY_WHEN_MARKET_CLOSED` |
| Advisory block | `should_block_new_buy` | `RISK_ADVISORY` → block **new** BUY |
| Capacity | `MAX_POSITIONS = 12` | Hard |
| Sizing | `get_dynamic_trade_size` | `cash / min(candidates, slots)`; clamp later 250–2500 |
| Cash check | `get_cash_available` + clamp in `buy_position` | No `MIN_CASH_RESERVE` in live |
| Duplicate ticker | **`if ticker not in positions`** | **Rebuy while open = blocked** |
| Execute | `buy_position` | Appends ledger row; Telegram |
| Portfolio update | `save_portfolio` → `portfolio.csv` | Cost on BUY row (`Price`,`Shares`,`Invested`) |
| Opening-noise / E3 | **Not on live path** | Paper only |

### 3.2 PAPER (TAE decision brain)

```text
market data / signals / memory / weights
  → tae_paper_decision_engine (PDE) — one final action per ticker
       hard-risk pre-entry; learning biases; held vs flat scoring
  → tae_decision_state (active_decisions.json) — churn / switch gates
  → tae_paper_execution.execute_decision
       fill-time hard risk; opening-noise; E3 PROFIT_DECAY
       _buy_shares / _sell_shares → paper_portfolio.json + orders jsonl
```

| Concern | Behavior |
|---------|----------|
| BUY scoring when held | PDE **does not** boost `BUY_PAPER` on held path — scale-in not decisioned today |
| Exec add-on | `_buy_shares` **can** weighted-average into existing position if BUY arrives |
| Idempotency | `processed_decision_ids` + reconcile after non-terminal skips |
| Capital | Confidence × cash (~5–15%); **no hard MAX_POSITIONS=12** in paper exec |

### 3.3 Same-ticker / average-cost today

| Book | Multiple BUY while open | Avg cost |
|------|-------------------------|----------|
| LIVE | **Forbidden** by gate | Computed FIFO `avg_price` in `get_open_positions` (supports multiple lots **if** they existed; gate prevents new lots) |
| PAPER | Decision avoids; exec allows | Persisted `positions[ticker].avg_price` weighted |

**Conclusion:** Infrastructure can *mathematically* average cost; Strategy V1 *policy* forbids live scale-in. No tranche budget / cycle state exists.

---

## 4. Fluxul SELL actual

### 4.1 LIVE priority (per open ticker)

| Priority | Source | Function | Exit |
|----------|--------|----------|------|
| 0 | `TEST_SELL_MODE` | `manage_portfolio` | Full |
| 1 | Mechanical stop `pnl ≤ −3%` | `core.trailing.evaluate_position_exit` → `SELL_STOP_LOSS` | Full |
| 2 | Trailing (activate at +5% PnL, trail 3%, min lock +2%) | same → `SELL_TRAILING` | Full |
| 3 | Signal `TAKE PROFIT` (RSI>70) | Ignored if trailing active or PnL ≥ activate | Full |
| 4 | Independent risk pass | `manage_position_risk_independent` (signal=`WAIT`) | Full |

**Conceptual note:** `TAKE_PROFIT_PCT = 5` **activates trailing**; it is not a fixed +5% full liquidation of strategy intent in the modern path.

**Partial exit LIVE:** **No** — `sell_position` always closes all open shares.

**Advisory SELL:** informational only; does not force live SELL.

### 4.2 PAPER exits

| Source | Path |
|--------|------|
| Hard risk STOP −3% / CRITICAL −5% | `hard_risk_guardian` → PDE `enforce_hard_risk_discipline` + fill-time |
| PDE scores | `SELL_PAPER`, `REDUCE_PAPER`, `PROTECT_PAPER`, `HOLD_PAPER` |
| Partial | `REDUCE_PAPER` / protect trim (~10%) via `_sell_shares(partial)` |
| Churn / reentry | `STOP_REENTRY_CHURN` cooldown bias after SELL |

### 4.3 Realized PnL & memory

| Book | Realized PnL | After close |
|------|--------------|-------------|
| LIVE | `(price − avg_price) * shares` on SELL row | Position disappears from `get_open_positions`; history remains in CSV |
| PAPER | Trade ledger + portfolio cash/realized fields | Longitudinal / learning memories optional |

---

## 5. Constante și praguri active

| Constant | File | Default | Active where | Notes |
|----------|------|---------|--------------|-------|
| `MIN_SCORE_TO_BUY` | `live_bot.py` | **80** | LIVE | Canonical live |
| `MIN_SCORE_TO_BUY` | `config/settings.py` | **90** | `core/risk.py` only | **Divergent / unused by live** |
| `STOP_LOSS_PCT` | `live_bot.py` / `core/trailing.py` | **−3** | LIVE exits | Strategy mechanical stop |
| Hard STOP / CRITICAL | `hard_risk_guardian.py` | **−3 / −5** | PAPER | Safety stack |
| `TAKE_PROFIT_PCT` | `live_bot.py` | **5** | LIVE = trailing activate | Not fixed full TP |
| `TRAILING_ACTIVATE_PCT` | `core/trailing.py` | 5.0 | Shared defaults | |
| `TRAILING_DISTANCE_PCT` | `live_bot.py` | **3** | LIVE | settings has **5** (unused by live) |
| `MIN_LOCKED_PROFIT_PCT` | live / trailing | **2** | LIVE trailing floor | |
| `MAX_POSITIONS` | `live_bot.py` | **12** | LIVE | |
| `MAX_POSITIONS_BULL/NEUTRAL/BEAR` | settings | 15/8/0 | legacy risk path | Not live |
| `MIN/MAX_TRADE_USD` | `live_bot.py` | 250 / 2500 | LIVE buy clamp | |
| `STARTING_CAPITAL` | live **30000** / settings **20000** | LIVE cash math | Fork |
| `MIN_CASH_RESERVE` | settings **500** | `core/risk.py` | **Not in live_bot** |
| Opening noise / E3 flags | `tae_paper_execution` env | default true | PAPER fills (new BUY) | |
| `STOP_REENTRY_CHURN` | PDE biases | ~30m evidence | PAPER | Not live constant |
| Per-ticker budget / max company capital | — | **absent** | — | V2 gap |
| Explicit rebuy cooldown (live) | — | **absent** | — | Shadow A/Bs only |

Call-sites for live exits: `live_bot._evaluate_open_position_exit`, `manage_portfolio`, `manage_position_risk_independent` → `core.trailing.evaluate_position_exit`.

---

## 6. Modelele de date existente

### 6.1 `portfolio.csv` (LIVE)

Columns:  
`Date,Ticker,Action,Price,Shares,Score,Signal,Reason,Current_Price,Invested,Current_Value,PnL,PnL_%,Highest_Price,Trailing_Active,Trailing_Stop`

| V2 need | Present? |
|---------|----------|
| Max budget / company | **No** |
| Budget used / remaining | **No** (only implicit cash + Invested rows) |
| Tranche count / per-tranche price-qty | **No** (BUY rows are events; not labeled as tranches) |
| Average cost | **Computed**, not a column |
| Next-tranche reference price | **No** |
| Cycle state / thesis valid | **No** |
| Partial exit records | **No** (SELL = full) |
| Successive cycles same ticker | Possible historically via BUY→SELL→BUY sequence, **not** modeled as cycles |

### 6.2 PAPER `paper_portfolio.json`

- `cash`, `positions[ticker].{shares, avg_price, ...}`, `processed_decision_ids`
- Can represent multi-fill average cost and partial sells
- **No** first-class: `max_budget`, `tranches[]`, `cycle_id`, `thesis_status`, `target_economic`

### 6.3 Decision / accounting / memory

| Store | Useful for V2? |
|-------|----------------|
| `active_decisions.json` | Switch authorization; not cycle economics |
| `paper_decisions.json` | Action + decision_id; extendable |
| `tae_accounting_snapshot.json` | Ledger compare; not tranche-aware |
| Longitudinal / DPE events | Outcome memory; not company budget |
| DPE `execution_jobs.jsonl` | Parallel philosophy jobs — **reuse pattern**, not V2 semantics |

**Do not invent new tables until extending paper position schema + optional cycle journal under `runtime_outputs/`.** LIVE CSV should remain V1 benchmark until deliberate promotion.

---

## 7. Suportul actual pentru tranșe și average cost

| Capability | LIVE V1 | PAPER today | Gap for V2 |
|------------|---------|-------------|------------|
| Tranche BUY policy | Blocked | Decision blocked; exec capable | Need decision owner for `ADD_TRANCHE` |
| Average cost | Computed FIFO | Weighted `avg_price` | OK mathematically |
| Company max budget | Absent | Absent | **Must add** (config + enforcement) |
| Partial exit | Absent | Present (`REDUCE`) | LIVE gap if promoting later |
| Cycle OPEN/CLOSE | Absent | Absent | **Must add** state machine |
| Feature flag strategy switch | Absent for V2 | E3/opening-noise flags exist as pattern | Reuse flag pattern; DPE flags are separate |

---

## 8. Duplicări și conflicte

| Item | Nature |
|------|--------|
| `live_bot.py` vs `config/settings.py` | **Divergent constants** (score 80 vs 90, capital 30k vs 20k, trailing 3 vs 5) |
| `core/risk.py` | Legacy / unused by live |
| Live stop vs paper hard-risk | Overlapping −3%; paper adds −5% CRITICAL |
| `core/portfolio.get_open_positions` vs `live_bot.get_open_positions` | **Divergent lot math** after sells; live does not call core.portfolio |
| PDE held BUY vs paper `_buy_shares` | Decision/exec **divergence** |
| Advisory vs PDE | Advisory gates live BUY; PDE owns paper — separate |
| DPE dual philosophy | Parallel paper books; **not** Investment Cycle V2 |
| Shadow A/B experiments | Research-only; must not be mistaken for runtime |

---

## 9. Punctul minim de integrare V2

### Recommended owner (extend, do not duplicate)

**Primary:** `tae_paper_decision_engine.py` — sole final-action brain for PAPER.  
**Secondary:** `tae_paper_execution.py` — already has avg-cost add-on + partial sell + idempotency.  
**Parallel book pattern (optional):** DPE execution splitter / isolated portfolios — prove V2 vs V1 without touching live.  
**Accounting compare:** `tae_accounting_snapshot` + `canonical-vs-paper` stay read-only comparators.

### Minimal architecture

```text
Existing TAE candidates (signals / ranking / allocation hints)
        │
        ▼
┌───────────────────────────────────────────┐
│ Strategy V2 Policy (NEW thin layer OR     │
│ PDE branch behind STRATEGY_V2_ENABLED)    │
│   OPEN_CYCLE | ADD_TRANCHE | HOLD         │
│   STOP_ACCUMULATION | EXIT_PARTIAL*       │
│   CLOSE_CYCLE                             │
└───────────────────────────────────────────┘
        │ authorized decisions
        ▼
tae_decision_state → tae_paper_execution (V2 ledger / tagged fills)
        │
        ├── V1 PAPER path unchanged when flag OFF
        └── LIVE live_bot.py UNCHANGED (V1 benchmark)
```

\* `EXIT_PARTIAL` only on PAPER (infra safe). Do not require live partial for V2 MVP.

### Decision mapping

| V2 decision | Maps to today | Notes |
|-------------|----------------|-------|
| `OPEN_CYCLE` | `BUY_PAPER` on flat | Plus cycle metadata |
| `ADD_TRANCHE` | new held-path BUY | Requires PDE change + budget checks |
| `HOLD` | `HOLD_PAPER` | |
| `STOP_ACCUMULATION` | HOLD + flag | No more ADD |
| `EXIT_PARTIAL` | `REDUCE_PAPER` | PAPER only |
| `CLOSE_CYCLE` | `SELL_PAPER` | Full close; preserve hard-risk override |

### Activation

- Feature flag default **false** (e.g. `STRATEGY_V2_ENABLED` in config JSON).
- When OFF: V1 SELL/BUY paths unchanged.
- Separable ledger: paper portfolio tag / isolated DPE-style store — **do not merge** into `portfolio.csv`.

**Do not** place V2 first in `live_bot.py`. That file is the V1 benchmark and protected runtime.

---

## 10. Fișierele care ar trebui modificate ulterior

*(Future implementation only — not this sprint.)*

| Priority | File | Why |
|----------|------|-----|
| P0 | New thin policy module **or** gated branch in `tae_paper_decision_engine.py` | Cycle decisions |
| P0 | `tae_paper_execution.py` | Enforce per-company budget; tag tranches; refuse over-budget ADD |
| P0 | Feature-flag config (new JSON under runtime_outputs or tae config) | Safe on/off |
| P1 | Paper portfolio schema docs + tests | `tranches`, `cycle_state`, `budget_*` |
| P1 | Replay harness (extend chrono or paper cycle) | V1 vs V2 A/B |
| P2 | DPE splitter arm (optional) | Isolated competitive book |
| P2 | Accounting compare tags | Separable economics |
| Later (promotion only) | `live_bot.py` / `core/trailing.py` | Only after PAPER evidence + governance unlock |

---

## 11. Fișierele care nu trebuie atinse

| File / class | Reason |
|--------------|--------|
| `live_bot.py` | V1 benchmark / LaunchAgent runtime |
| `portfolio.csv` / `live_signals.csv` / `watchlist.txt` | LIVE SSOT |
| `core/trailing.py` | V1 exit policy SSOT until promotion |
| Hard-risk **limits** in `hard_risk_guardian.py` | Safety floor — keep |
| Closed-hypothesis experiment modules as “fixes” | Do not reopen STOP/REBUY/B1/sizing as V2 substitutes |
| `migration/`, casual `research/` imports into production | Isolation |
| Merging LIVE ↔ PAPER ledgers | Forbidden |

---

## 12. Riscurile și controalele obligatorii

### Separate risk layers (do not collapse)

| Layer | Role in V2 | Recommendation |
|-------|------------|----------------|
| Strategy mechanical −3% stop | V1 strategy exit | May be replaced **in V2 policy** by thesis/budget exits — **only behind flag, PAPER first** |
| Fixed +5% take-profit | Already non-primary (trailing activate) | V2 may omit fixed TP |
| Trailing | V1 profit lock | Optional in V2; evaluate separately |
| **Hard-risk safety (−3/−5 paper)** | Capital protection | **KEEP always** |
| Thesis invalidation | Missing today | **Mandatory V2 control** before removing mechanical stop |
| Max capital / company | Missing | **Mandatory** to prevent cash sink |
| Data corruption / NaN / stale marks | Existing paper age gates | Keep |
| Delist / insolvency / FX / splits | Accounting / market data layer | Keep integrity replay rules |

### Specific risks

| Risk | Control |
|------|---------|
| Averaging into deterioration | Thesis invalid → `STOP_ACCUMULATION` / `CLOSE_CYCLE`; hard-risk still forces exit |
| Cash exhaustion in prolonged decline | Hard max budget/company + global cash reserve + max open cycles |
| Correlation cluster | Reuse exposure/regime advisories; do not ignore RISK_ADVISORY patterns |
| Reserved unused budgets | Budget release on `STOP_ACCUMULATION` / timeout |
| Cash competition | Single allocator order (existing candidate ranking); no retrospective reallocation |
| Duplicate BUY / repeated fills | Keep `decision_id` idempotency; tranche_id uniqueness |
| Race / stale price | Existing mark age / session gates |
| FX / GBp / splits | Existing integrity replay; tranche notionals in USD ledger |
| Multi-tranche PnL | Realized on partial/full via avg_price; journal per tranche for attribution |
| Exit before profit if thesis dies | Explicit `CLOSE_CYCLE` on invalid thesis — **required** if mechanical stop removed |
| Removing all loss protection | **Forbidden** — hard-risk retained |

---

## 13. Planul de implementare în pași atomici

1. **Schema PAPER cycle** — add optional fields (`cycle_id`, `budget_max`, `budget_used`, `tranches[]`, `state`) without breaking V1 readers.  
2. **Flag OFF harness** — prove identical V1 paper behavior when `STRATEGY_V2_ENABLED=false`.  
3. **Policy MVP** — `OPEN_CYCLE` / `ADD_TRANCHE` / `HOLD` / `STOP_ACCUMULATION` / `CLOSE_CYCLE` only (no live).  
4. **Budget enforcement** in execution before fill.  
5. **Hard-risk unchanged** — regression tests.  
6. **EXIT_PARTIAL** only if reduce path covered by tests.  
7. **Replay / PAPER A/B** V1 vs V2 isolated ledger.  
8. **Economic gates** (Phase X) before any live discussion.  
9. **Promotion design** (separate sprint) — never silent live_bot edit.

---

## 14. Testele necesare (viitor)

- Flag OFF ⇒ bit-identical V1 paper decisions/fills on fixture.  
- `OPEN_CYCLE` creates cycle + consumes budget.  
- `ADD_TRANCHE` blocked when budget exhausted / thesis invalid / hard-risk breached.  
- Idempotent `decision_id` / `tranche_id`.  
- Avg cost after 2–3 tranches.  
- Partial reduce then close; realized/unrealized reconcile.  
- Hard-risk still forces `SELL`/`CLOSE_CYCLE`.  
- LIVE `live_bot.py` hash unchanged.  
- No write to `portfolio.csv` from V2 path.  
- FX / GBp / split fixtures.  
- Cash competition: two candidates, deterministic winner.  
- Stale/NaN price → no ADD.

*(This audit sprint did not run mutating paper/integrity suites.)*

---

## 15. Criterii de acceptare și rollback

### Acceptare (implementation sprint)

- V1 LIVE untouched; flag default false.  
- V2 PAPER ledger separable; morning-audit / canonical-vs-paper still valid.  
- Hard-risk paths green.  
- Budget + thesis controls present before any mechanical-stop removal in V2.  
- Economic evidence required for promotion (Phase X).

### Rollback

- Set `STRATEGY_V2_ENABLED=false` (instant).  
- Do not delete V1 code paths.  
- Discard/ignore V2 paper ledger; resume V1 paper cycle.

---

## 16. Verdict final

### `READY_WITH_BLOCKERS`

**Why not fully READY:** missing cycle/tranche/budget schema; live same-ticker lock; live no partial exit; PDE held-path cannot ADD; constant forks; thesis invalidation absent; mechanical-stop removal unsafe without hard-risk + thesis + budget triad.

**Why not NOT_READY:** owners are clear; paper already has avg-cost + partial + idempotency; DPE shows parallel-book pattern; dual-ledger governance exists; minimal hook is PDE+execution behind a flag — no ecosystem rewrite required.

---

## Appendix A — Canonical owners (summary)

| Concern | Owner |
|---------|-------|
| Canonical BUY (LIVE) | `live_bot.manage_portfolio` / `buy_position` |
| Canonical SELL (LIVE) | `live_bot` + `core.trailing` |
| PAPER decisions | `tae_paper_decision_engine.py` |
| PAPER execution | `tae_paper_execution.py` |
| Replay | `tae_chronological_portfolio_replay.py` (+ decision replay composer) |
| Accounting | `tae_accounting_snapshot.py` |
| Position state LIVE | Derived from `portfolio.csv` via `get_open_positions` |
| Position state PAPER | `paper_portfolio.json` |

## Appendix B — Proposed integration point (one line)

**Feature-flagged Strategy V2 policy feeding PDE/paper execution (and optionally a DPE isolated book), leaving `live_bot.py` as immutable V1 benchmark until Phase X promotion.**
