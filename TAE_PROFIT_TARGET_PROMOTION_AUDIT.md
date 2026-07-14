# TAE Profit Target Adapter Promotion Audit

**Generated:** 2026-07-14  
**Verdict:** `PROFIT_TARGET_PROMOTED`  
**Machine-readable:** `tae_profit_target_promotion_audit.json`

---

## Summary

Promoted the **existing** Profit Target Adapter (`tae_profit_target_adapter.json`) into the PAPER Decision Brain via minimal PDE wiring. No new module, no execution changes, no new profit logic.

---

## Phase 1 — Adapter audit (existing outputs)

| Output | Verified |
|--------|----------|
| `exit_window_urgency` | LOW / MEDIUM / HIGH / CRITICAL |
| `dynamic_partial_tp_pct` | Per-ticker partial take-profit threshold |
| `dynamic_trailing_pct` | Trailing stop guidance |
| `dynamic_profit_lock_pct` | Profit lock threshold |
| `hold_ceiling_pct` | Max hold run-up ceiling |
| `min_capture_pct` | Minimum capture target |
| `suggested_partial_size_pct` | Trim/protect size (20–50%) |
| `target_confidence` | 0–1 confidence score |
| `recommended_shadow_strategy` | KEEP_GROWING / HOLD_AND_MONITOR / PROTECT / TIGHTEN / REDUCE |
| `recovery_exit_management_only` | COLLAPSED recovery flag |
| `growth_score` | Upstream GII score |
| Portfolio aggregates | Policy, dominant mode, avg targets |

**Global verdict:** `PROFIT_TARGET_ADAPTER_READY` · **16 tickers**

---

## Phase 2 — PDE wiring

**Module:** `tae_paper_decision_engine.py`

- `build_context()` loads `tae_profit_target_adapter.json` → `profit_target_by`
- `apply_profit_target_adapter_bias()` applies score deltas for **held positions only**
- Influences: `HOLD_PAPER`, `PROTECT_PAPER`, `REDUCE_PAPER`, `SELL_PAPER` (urgency-weighted)
- Does **not** touch `BUY_PAPER`
- Runs **after** hard-risk override path; **before** conflict resolution and decision-state gate
- Recorded in `profit_target_evidence` on each decision

**Preserved:** Hard Risk · Decision State · Conflict Resolution · Profit Integrity · Reconciliation

---

## Phase 3 — Replay (baseline vs integrated)

| Metric | Baseline | Integrated | Δ |
|--------|----------|------------|---|
| Profit vs $30k base | -$185.30 | -$182.41 | **+$2.89** |
| Max drawdown | 1.73% | 1.72% | -0.01pp |
| Missed profit avoided | — | $2.89 | CRITICAL trims on QQQ, HSBA.L |
| Profit factor | 0.0 | 0.0 | unchanged (4 closed losses) |

---

## Phase 4 — Promotion checks

| Check | Result |
|-------|--------|
| Higher profit | **PASS** (+$2.89 vs base) |
| Drawdown ≤ baseline | **PASS** |
| Profit Integrity | **PASS** |
| Reconciliation | **PASS** |
| Churn regression | **PASS** (no new BUY creation) |
| promotion_lock | **false** |

---

## Validation

```bash
python3 tae.py full-paper-cycle    # PASS
python3 tae.py profit-pipeline     # integrity PASS, reconciliation PASS
python3 tae.py morning-audit       # PAPER_PROFIT_INTEGRITY PASS
python3 -m unittest tae_paper_decision_engine_test tae_profit_target_promotion_test \
  tae_profit_pipeline_test tae_paper_execution_test -v  # 49 OK
```

**Live decisions:** HSBA.L and QQQ show `profit_target_evidence.applied=true` with `CRITICAL` urgency → `PROTECT_PAPER`.

---

## Files changed

- `tae_paper_decision_engine.py` — PTA load + bias function
- `tae_paper_decision_engine_test.py` — wiring tests
- `tae_profit_target_promotion.py` — replay helper
- `tae_profit_target_promotion_test.py` — replay tests

**Unchanged:** `tae_profit_target_adapter.py`, execution, portfolio, hard risk, decision state.
