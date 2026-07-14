# TAE Decision Risk Synchronization Audit

**Generated:** 2026-07-14  
**Verdict:** `MAIN_BRAIN_RISK_SYNCHRONIZED`  
**Mode:** PAPER_ONLY · NO_BROKER · NO_LIVE_PROMOTION

---

## Root cause

The Main Decision Brain produced **internally contradictory actions** because:

1. **Pre-entry gap:** `enforce_hard_risk_discipline()` only overrides when a **held** position already breached `-3%` / `-5%`. It did not evaluate whether a proposed **BUY** was compatible with existing risk intelligence.
2. **Insufficient BUY penalties:** Under `HIGH_RISK`, PDE applied only `-8 BUY / +15 SKIP` while `STRONG BUY` signal added `+40` and top-growth added `+20`.
3. **Exposure blind spot:** When `paper_positions` lagged behind accounting/live exposure, PDE used the **flat** entry path and authorized add-on BUYs on names already structurally decaying (`PROFIT_DECAY`, `collapse_probability=1.0`, `TIGHTEN_TRAIL_SHADOW`).
4. **Reentry churn:** `STOP_REENTRY_CHURN` 30-minute cooldown expired on AMAT Jul 9 while GII risk profile remained critical.

**Detectable before execution:** Yes — GII, PPG, APPE, Hard Risk status, and live exposure were all available; PDE did not consume collapse/lifecycle for pre-entry BUY gating.

---

## Synchronization (existing components only)

| Step | Component | Change |
| --- | --- | --- |
| 1 | `evaluate_pre_entry_hard_risk_compatibility()` | Thin evidence function reusing Hard Risk, GII, PPG, decision-state cooldown, paper orders |
| 2 | `apply_pre_entry_hard_risk_sync()` | Hard block (zero BUY) or soft score delta before conflict resolution |
| 3 | `score_actions_for_ticker()` | Wired between loss discipline and conflict resolution; final BUY veto after decision state |
| 4 | `build_decision()` | Coherence payload on every decision |
| 5 | `build_context()` | Loads `recent_hard_stops_by_ticker` from `paper_orders.jsonl` |

**Hard blocks:** active breach, hard-stop cooldown, persistent critical risk after hard stop, critical collapse + profit decay + HIGH_RISK, TIGHTEN_TRAIL + critical collapse, existing exposure + structural decay, insufficient stop cushion, missing mark.

**Soft penalties:** elevated collapse / weak lifecycle under HIGH_RISK — score delta only; conflict resolution runs after adjustment.

**Hard Risk SELL:** unchanged — mandatory override bypasses all soft gates.

---

## Validation

| Check | Result |
| --- | --- |
| `decision-state-refresh` | PASS |
| `full-paper-cycle` × 2 | PASS |
| `profit-pipeline` | PASS · reconciliation **PASS** |
| `morning-audit` | **READY** |
| `profit-optimization` | CURRENT_BRAIN_RETAINED_INSUFFICIENT_EVIDENCE |
| Profit Integrity | **PASS** |
| Capital base | **$30,000** |
| Promotion lock | **false** |
| Unit tests | **88 OK** (12 new regression tests) |
| BUY + `BLOCKED_HARD_RISK_CONFLICT` | **0 violations** |

---

## Current cycle decisions (target tickers)

| Ticker | Action | Coherence |
| --- | --- | --- |
| AMAT | SKIP_PAPER | BLOCKED_HARD_RISK_CONFLICT |
| MU | SKIP_PAPER | BLOCKED_HARD_RISK_CONFLICT |
| SIE.DE | HOLD_PAPER | COHERENT |
| QQQ | PROTECT_PAPER | COHERENT |
| HD | HOLD_PAPER | COHERENT (flat replay: BUY_PAPER allowed) |

**BUYs blocked:** 3 (AMAT, MU, HSBA.L)  
**Clean replay prevented loss:** $308.50 (LOSS-001 + LOSS-002 + LOSS-005 entry avoidance)

See also: `TAE_FORENSIC_LOSSES_BEFORE_AFTER.md` · `tae_forensic_losses_before_after.json`
