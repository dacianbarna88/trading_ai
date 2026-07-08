# TAE PAPER Capital Base Defect Audit

**Date:** 2026-07-08  
**Verdict:** `PAPER_CAPITAL_BASE_FIXED` (after patch + reset)  
**Mode:** PAPER_ONLY · AUDIT_FIRST · NO_STRATEGY_CHANGES

---

## Executive summary

Day 1 30-day PAPER profit validation reported **$51,442.97** account value and **$21,102.05** total PnL against an expected **$30,000** contributed capital base (canonical accounting **$30,340.91**). The ~**$21,102** gap is not double-counting of cash + positions + PnL — internal formulas reconcile. The inflation comes from a **synthetic $100.00 fill-price fallback** in `tae_paper_execution.py` that booked fake realized and unrealized profit when new tickers were bought without a mark price.

---

## Observed Day 1 (INVALID — superseded)

| Metric | Reported (corrupt) | Expected |
| --- | ---: | ---: |
| Paper account value | $51,442.97 | ~$30,340.91 |
| Cash | $24,583.88 | $2,335.28 (canonical) |
| Realized PnL | $14,870.56 | ~$0 at validation reset |
| Unrealized PnL | $6,231.49 | ~$192.58 (canonical) |
| Total PnL | $21,102.05 | ~$340.91 vs $30k base |
| Starting value (stored) | $30,057.82 | $30,000.00 |
| Canonical reference | $30,340.91 | — |
| Paper − Canonical delta | **$21,102.06** | — |

---

## Mathematical proof (corrupt state)

### Account value decomposition

```
cash               = $24,583.88
open_positions     = $26,859.10
total_value        = $51,442.97   ✓  (cash + open_positions)
```

### PnL decomposition

```
realized_pnl       = $14,870.56
unrealized_pnl     = $ 6,231.49
total_pnl          = $21,102.05   ✓  (realized + unrealized)
```

### Cross-check vs canonical

```
canonical account_value_corrected     = $30,340.91
effective_contributed_capital         = $30,000.00
paper total_value − canonical         = $21,102.06  ≈ total_pnl reported
```

Internal PAPER formulas are **internally consistent**; the defect is **bad fill prices in the trade ledger**, not `cash + positions + pnl` double-counting.

---

## Root cause: synthetic $100 fills

**Location:** `tae_paper_execution.py`

| Function | Defect (pre-fix) |
| --- | --- |
| `price_for_ticker()` | Returned `100.0` when no accounting/decision price |
| `fill_price_for_position()` | Returned `100.0` (and `avg_price`) when no MTM price |

**Mechanism:** `BUY_PAPER` on tickers absent from canonical `open_positions` (e.g. AIR.PA, DIA, GE, HD) executed at **$100/share**. Subsequent `SELL_PAPER` at real MTM (e.g. HD $336, DIA $522) produced massive fake realized PnL. Open positions still held at **avg_price = $100** retained fake unrealized PnL after MTM.

### Synthetic inflation quantified

| Source | Count | Fake PnL |
| --- | ---: | ---: |
| `BUY_PAPER` at exactly $100 | 12 | — |
| Sells with $100 cost basis | 9 | **$15,706.29** realized |
| Open positions avg_price = $100 | 3 (AIR.PA, DIA, GE) | **$6,157.59** unrealized |
| **Combined synthetic** | — | **~$21,864** |

Delta paper − canonical (**$21,102**) matches combined synthetic inflation within mixed legitimate trades.

### Example trade chain (HD)

1. `BUY_PAPER` @ **$100.00** → cost basis $501.82  
2. `SELL_PAPER` @ **$335.77** → realized **+$1,183.13** (fake; true basis should be ~$336)

---

## Contributing factors (not primary cause)

| Check | Result |
| --- | --- |
| Duplicated trades | No — distinct decision_ids / timestamps |
| Old paper history mixed into baseline | Yes — pre-validation churn on 2026-07-08 inflated cumulative realized |
| Realized PnL double counted in total_value | No — total_value = cash + positions only |
| cash + positions + pnl triple-count | No — formulas reconcile |
| Canonical vs PAPER SSOT mismatch | Yes — PAPER diverged from canonical by ~$21k |
| Validation report wrong field | Yes — used inflated `total_value` as Day 1 baseline |
| `bootstrap_portfolio()` preserved corrupt state | Yes — returned existing portfolio when schema matched |
| `ensure_accounting_baseline()` | Set `starting_value` from inflated `total_value` on first run |

---

## Fix applied (minimal, PAPER accounting only)

**File:** `tae_paper_execution.py`

1. Removed **$100.00** synthetic defaults from `price_for_ticker()` and `fill_price_for_position()`.
2. `BUY_PAPER` without mark price → `SKIPPED_NO_MARK_PRICE` (no trade).
3. Added `paper_portfolio_has_synthetic_fill_corruption()` + `reset_paper_portfolio_from_accounting()`.
4. Auto-reset on corruption at `run_paper_execution()` start; archives corrupt ledger to `runtime_outputs/paper_execution/archive/capital_base_defect_reset/`.
5. `starting_value` anchored to `effective_contributed_capital` (**$30,000**), not inflated totals.
6. `ensure_accounting_baseline()` uses validation capital base, not current `total_value`.

**Not changed:** PDE decisions, strategy, decision logic, new modules.

---

## Day 1 validation status

| Item | Status |
| --- | --- |
| Day 1 session 2026-07-08T20:40 | **INVALID / SUPERSEDED** |
| Reason | Baseline captured corrupt $51,442.97 portfolio |
| Action | Reset from canonical accounting; re-establish baseline post-fix |

---

## Machine-readable audit

See `tae_paper_capital_base_defect_audit.json`.
