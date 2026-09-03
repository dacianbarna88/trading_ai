# TAE Accounting Reconciliation Report

**Date:** 2026-07-07  
**Mode:** READ_ONLY · NO_BROKER · NO_EXECUTION · NO_LIVE_CHANGE · NO_COMMIT  
**Source:** `tae_accounting_snapshot.json` (read-only audit)

---

## Executive summary

| Item | Status |
|------|--------|
| `data_quality_status` | `HISTORICAL_RECONCILIATION_REQUIRED` |
| Canonical account value | **Reconciled** (`account_value_reconciliation_delta = 0.0`) |
| Missing accounting | **None** — snapshot present and complete |
| Duplicated accounting | **Controlled** — virtual deposit excluded from capital base |
| Stale accounting | **Partial** — historical SELL `PnL` column stale; corrected path active |
| Inconsistent accounting | **Historical only** — 28/44 SELL rows; live metrics use corrections |

**Verdict:** Canonical morning metrics are **reconciled and safe to use**. The `HISTORICAL_RECONCILIATION_REQUIRED` flag documents legacy ledger noise, not a current balance failure.

---

## Trigger: why `HISTORICAL_RECONCILIATION_REQUIRED`

From `research_core/accounting/accounting_snapshot.py`:

```text
if sell_mismatch_count > 0:
    data_quality = "HISTORICAL_RECONCILIATION_REQUIRED"
```

Current snapshot:

| Field | Value |
|-------|-------|
| `sell_mismatch_count` | 28 |
| `sell_row_count` | 44 |
| `corrected_realized_pnl` | $148.33 |
| `corrected_unrealized_pnl` | $192.58 |
| `corrected_total_trading_pnl` | $340.91 |
| `account_value_corrected` | $30,340.91 |
| `account_value_reconciliation_delta` | **0.0** |

The flag means **reported PnL on old SELL rows does not match FIFO-expected realized PnL**. All canonical totals use **corrected** values, not stale column values.

---

## Category audit

### 1. Missing accounting — **NONE**

| Check | Result |
|-------|--------|
| `tae_accounting_snapshot.json` exists | ✅ |
| `portfolio.csv` readable | ✅ (`portfolio_readable: true`) |
| Open positions populated | ✅ 12 positions |
| Capital base block present | ✅ |
| Winners/losers corrected lists | ✅ |

No missing SSOT artifact blocks morning reporting.

---

### 2. Duplicated accounting — **CONTROLLED (not double-counting)**

| Issue | Finding |
|-------|---------|
| Virtual deposit detected | $10,000 (`VIRTUAL CAPITAL TEST`, `NON_TRADING_VIRTUAL`) |
| Counted in effective capital | **No** — excluded from `effective_contributed_capital` |
| `capital_deposits_excluded_as_duplicate` | $10,000 |
| `double_count_detected` | `false` |
| `capital_base_status` | `NEEDS_OPERATOR_CONFIRMATION` |

**Interpretation:** A test/virtual deposit exists in `portfolio.csv` but is **intentionally excluded** from contributed capital. Canonical cash path uses `starting_capital_config` ($30,000) without inflating cash to $12,335.

**Risk if mishandled:** Adding all deposits would raise `cash_if_all_deposits_counted` to $12,335.28 while `live_bot.py` ignores DEPOSIT rows — documented in `capital_base_explanation`.

**Operator action (non-urgent):** Confirm virtual deposit classification remains `NON_TRADING_VIRTUAL`.

---

### 3. Stale accounting — **HISTORICAL SELL PnL COLUMN**

| Layer | Freshness | Notes |
|-------|-----------|-------|
| Snapshot `generated_at` | 2026-07-06T16:15:54+00:00 | Same-day |
| Open position marks | From `portfolio.csv` `Current_Price` | Active |
| Historical SELL `PnL` column | **Stale** | 28 rows mismatch expected FIFO PnL |
| Corrected realized PnL | **Current** | Recomputed via integrity auditor |

**Stale vs corrected delta:**

| Metric | Value |
|--------|-------|
| `reported_realized_pnl_stale` | -$861.22 |
| `corrected_realized_pnl` | +$148.33 |
| `corrected_vs_reported_delta` | -$1,009.55 |

**Root cause pattern (from top trades):**

| `consistency_status` | Count (top winners/losers sample) |
|----------------------|-----------------------------------|
| `MISMATCH_REASON_PNL` | 4 |
| `POSSIBLE_ACCOUNTING_BUG` | 5 |
| `OK` | 11 |

Common pattern: SELL row `PnL` column reflects mark-to-market or reason-string drift, not execution-time realized gain. Example — **GS** sell 2026-06-17:

- Reported PnL: **-$903.90**
- Expected realized PnL: **+$547.99**
- Delta: **-$1,451.89**

Canonical metrics use **+$547.99**.

---

### 4. Inconsistent accounting — **HISTORICAL ONLY; LIVE PATH CONSISTENT**

| Reconciliation check | Result |
|------------------------|--------|
| `cash + open_positions = account_value` | ✅ $2,335.28 + $28,005.63 = $30,340.91 |
| `effective_capital + corrected_pnl = account_value` | ✅ $30,000 + $340.91 = $30,340.91 |
| `account_value_reconciliation_delta` | ✅ 0.0 |
| `execution_integrity_status` | `MISMATCH_DETECTED` (historical sells only) |

**Not inconsistent for operations:**

- Morning audit portfolio totals
- DPE decision event `account_snapshot`
- Growth / PPG / protection engines consuming `tae_accounting_snapshot.json`

**Inconsistent for audit trail only:**

- Raw `portfolio.csv` SELL `PnL` column on 28 historical rows
- `reported_realized_pnl_stale` aggregate

---

## Warnings in snapshot

```text
1. CAPITAL BASE NEEDS CONFIRMATION — see capital_base_explanation
2. 28 historical SELL row(s) have stale reported PnL — corrected values used for all canonical metrics
```

Both are **informational** given delta=0 reconciliation.

---

## Recommendations

### P0 — No live change required

1. **Continue using canonical snapshot fields** for all morning/ops reporting (`corrected_*`, `account_value_corrected`).
2. **Treat `HISTORICAL_RECONCILIATION_REQUIRED` as audit label**, not a trading blocker.

### P1 — Optional ledger hygiene (future, non-urgent)

1. Backfill or annotate the 28 historical SELL rows in `portfolio.csv` with corrected PnL (operator-approved migration only).
2. Confirm virtual $10K deposit remains excluded (`NEEDS_OPERATOR_CONFIRMATION` → `CONFIRMED`).
3. Re-run accounting snapshot after any ledger cleanup to flip `data_quality_status` to `OK`.

### Do not do

- Do not modify `live_bot.py` trading logic
- Do not rewrite historical rows without operator approval
- Do not count virtual deposit into effective capital

---

## Safety confirmation

| Rule | Status |
|------|--------|
| READ_ONLY audit | ✅ |
| NO_BROKER | ✅ |
| NO_LIVE_CHANGE | ✅ |
| NO_PORTFOLIO_CHANGE | ✅ |
| NO_COMMIT | ✅ |

---

## Sign-off

| Question | Answer |
|----------|--------|
| Missing accounting? | **No** |
| Duplicated accounting? | **Controlled exclusion** |
| Stale accounting? | **Historical SELL column only** |
| Inconsistent live totals? | **No — reconciled** |
| Safe for morning audit? | **Yes** |
