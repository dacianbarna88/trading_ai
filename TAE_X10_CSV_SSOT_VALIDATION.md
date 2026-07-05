# TAE X.10 CSV SSOT Validation

**Date:** 2026-07-05  
**Mode:** READ ONLY — no code changes, no commit  
**Primary SSOT:** `tae_shadow_validation_events.csv`  
**Validation time:** CSV read at report generation (append-only ledger — counts may drift between reads)

---

## Verdict

**PASS — X.10 scope and filtering are correct against CSV SSOT.**

| Check | Result |
|-------|--------|
| X.10 attributes only `BUY_BLOCKED_BY_TAE` | **PASS** (0 in CSV → 0 eligible) |
| `BUY_SKIPPED_OTHER_REASON` excluded from attribution | **PASS** (code + runtime leak check) |
| `eligible_events` matches CSV blocked count | **PASS** (0 = 0) |
| `policy_change_allowed` | **PASS** (`false`) |
| Zero blocked → `PENDING_NEXT_PHASE` | **PASS** (not FAIL) |

**Stale artifact mismatch (non-blocking):** On-disk `tae_shadow_validation_summary.json` and `TAE_X10_CHECKPOINT_VALIDATION_REPORT.md` reflect an **earlier CSV snapshot** (2550 rows) while the live CSV has grown to **2554 rows** via append-only bot logging. Re-run batch jobs to refresh JSON; **no X.10 logic defect**.

---

## 1. CSV overview

**File:** `tae_shadow_validation_events.csv`  
**Physical lines:** 2555 (1 header + 2554 data rows)  
**Data rows (SSOT):** **2554**

Schema (from `shadow_validation_ledger.py`):

`timestamp`, `ticker`, `event_type`, `signal`, `score`, `price`, `intended_trade_usd`, `shares`, `advisory_action`, `advisory_confidence`, `advisory_reasons`, `advisory_blockers`, `block_new_buy`, `block_reason`, `live_bot_cycle_id`, `mode`, `live_trading_impact`

Valid event types in ledger contract:

- `BUY_BLOCKED_BY_TAE`
- `BUY_ALLOWED`
- `BUY_SKIPPED_OTHER_REASON`

---

## 2. Event type distribution (CSV SSOT)

| `event_type` | Count | % of total |
|--------------|------:|-----------:|
| **`BUY_SKIPPED_OTHER_REASON`** | **2529** | 99.02% |
| **`BUY_ALLOWED`** | **25** | 0.98% |
| **`BUY_BLOCKED_BY_TAE`** | **0** | 0.00% |
| **Total** | **2554** | 100% |

**No other event types present** in the CSV at validation time.

---

## 3. Secondary field distributions

### `block_reason` (all rows)

| `block_reason` | Count | Typical `event_type` |
|----------------|------:|------------------------|
| `MARKET_SESSION_FILTER` | 2393 | `BUY_SKIPPED_OTHER_REASON` |
| `MAX_POSITIONS (12)` | 135 | `BUY_SKIPPED_OTHER_REASON` |
| *(empty)* | 25 | `BUY_ALLOWED` |
| TAE / `RISK_ADVISORY` block reasons | **0** | — |

### `advisory_action` (all rows)

| `advisory_action` | Count |
|-------------------|------:|
| `NO_ACTION` | 1856 |
| `SELL_ADVISORY` | 698 |

**Note:** No row has `advisory_action == RISK_ADVISORY` in the CSV. X.8 blocks are logged as `BUY_BLOCKED_BY_TAE` with `block_reason` like `TAE RISK_ADVISORY — new BUY blocked`; none exist yet.

### `block_new_buy` (all rows)

| Value | Count |
|-------|------:|
| `false` | **2554** |

All rows show `block_new_buy=false` because no `BUY_BLOCKED_BY_TAE` events exist; skips are non-TAE gates (session / max positions).

### Skip breakdown (`BUY_SKIPPED_OTHER_REASON` only)

| `block_reason` | Count |
|----------------|------:|
| `MARKET_SESSION_FILTER` | 2393 |
| `MAX_POSITIONS (12)` | 135 |

---

## 4. Specific verification

| Event type | CSV count | X.10 attributed? | Expected |
|------------|----------:|:-----------------:|----------|
| **`BUY_BLOCKED_BY_TAE`** | **0** | Yes (only this type) | `eligible_events = 0` |
| **`BUY_SKIPPED_OTHER_REASON`** | **2529** | **No** | Excluded |
| **`BUY_ALLOWED`** | **25** | **No** (sizing reference only) | Excluded from WIN/LOSS |
| Other types | 0 | No | N/A |

---

## 5. Representative sample rows

### 5 skipped / other (`BUY_SKIPPED_OTHER_REASON`)

| # | timestamp | ticker | signal | score | price | advisory_action | block_reason |
|---|-----------|--------|--------|------:|------:|-----------------|--------------|
| S1 | 2026-06-30T10:12:04Z | PG | STRONG BUY | 100 | 148.45 | SELL_ADVISORY | MARKET_SESSION_FILTER |
| S2 | 2026-07-01T16:56:34Z | AMAT | STRONG BUY | 80 | 653.15 | NO_ACTION | MAX_POSITIONS (12) |
| S3 | 2026-06-30T10:12:04Z | PM | STRONG BUY | 100 | 182.87 | SELL_ADVISORY | MARKET_SESSION_FILTER |
| S4 | 2026-06-30T10:42:03Z | PG | STRONG BUY | 100 | 148.45 | SELL_ADVISORY | MARKET_SESSION_FILTER |
| S5 | 2026-07-05T18:34:20Z | SIE.DE | STRONG BUY | 80 | 284.10 | SELL_ADVISORY | MARKET_SESSION_FILTER |

All samples: `event_type=BUY_SKIPPED_OTHER_REASON`, `block_new_buy=false`, `intended_trade_usd` empty.

### 5 allowed (`BUY_ALLOWED`) — all 25 share same pattern; first 5 shown

| # | timestamp | ticker | signal | score | price | intended_trade_usd | advisory_action |
|---|-----------|--------|--------|------:|------:|-------------------:|-----------------|
| A1 | 2026-06-30T09:10:15Z | ULVR.L | STRONG BUY | 80 | 4562.50 | 22574.18 | SELL_ADVISORY |
| A2 | 2026-06-30T13:30:07Z | PG | STRONG BUY | 100 | 148.45 | 5665.58 | SELL_ADVISORY |
| A3 | 2026-06-30T13:30:07Z | PM | STRONG BUY | 100 | 182.87 | 5665.58 | SELL_ADVISORY |
| A4 | 2026-06-30T13:30:08Z | MU | STRONG BUY | 80 | 1145.28 | 5665.58 | SELL_ADVISORY |
| A5 | 2026-06-30T13:30:08Z | DIA | STRONG BUY | 80 | 521.68 | 5665.58 | SELL_ADVISORY |

Control cohort only — **not** included in block outcome WIN/LOSS rates.

### Blocked (`BUY_BLOCKED_BY_TAE`)

**None.** Zero rows in CSV — no samples available.

---

## 6. Code filter verification (`shadow_outcome_attribution.py`)

### Attribution entry filter

```1004:1004:research_core/governance/shadow_outcome_attribution.py
    blocked = [e for e in events if e.get("event_type") == EVENT_BUY_BLOCKED_BY_TAE]
```

Only this list is passed to `evaluate_blocked_event()` → `records` → `resolved_events`.

### Scope emitted in report

```1041:1041:research_core/governance/shadow_outcome_attribution.py
        "scope_event_type": EVENT_BUY_BLOCKED_BY_TAE,
```

### `BUY_ALLOWED` usage (not attribution)

Used only for **median notional reconstruction** when blocked events lack `intended_trade_usd` — not evaluated for WIN/LOSS.

### Status when no blocked records

```985:988:research_core/governance/shadow_outcome_attribution.py
    if not records:
        return "PENDING_NEXT_PHASE"
    if not any(r.event_type == EVENT_BUY_BLOCKED_BY_TAE for r in records):
        return "PENDING_NEXT_PHASE"
```

**Conclusion:** Code filters **ONLY** `BUY_BLOCKED_BY_TAE`. **PASS**

---

## 7. Runtime leak check (fresh in-memory run against live CSV)

Executed read-only:

```python
events = load_events()  # 2554 rows at run time
outcomes = build_outcomes_report(events)
# resolved_events length = 0
# no event_type != BUY_BLOCKED_BY_TAE in resolved_events
```

| Check | Result |
|-------|--------|
| `len(resolved_events)` | 0 (= CSV blocked count) |
| Skip rows in `resolved_events` | **0** |
| `LEAK_CHECK` | **none** |

**PASS** — no `BUY_SKIPPED_OTHER_REASON` can enter attribution with current CSV.

---

## 8. Cross-artifact comparison

### CSV SSOT (this validation)

| Metric | CSV value |
|--------|-----------|
| Total data rows | **2554** |
| `BUY_BLOCKED_BY_TAE` | **0** |
| `BUY_SKIPPED_OTHER_REASON` | **2529** |
| `BUY_ALLOWED` | **25** |

### `tae_shadow_validation_outcomes.json` (on disk, generated 2026-07-05T18:30:44Z)

| Field | JSON value | CSV expected | Match? |
|-------|------------|--------------|--------|
| `scope_event_type` | `BUY_BLOCKED_BY_TAE` | — | ✓ |
| `eligible_events` | **0** | **0** | **✓** |
| `resolved_events` length | **0** | **0** | **✓** |
| `outcome_tracking_status` | `PENDING_NEXT_PHASE` | (0 blocked) | **✓** |
| `policy_change_allowed` | `false` | — | **✓** |

Outcomes JSON does **not** store total CSV row counts — only blocked cohort. **No logic mismatch.**

### `tae_shadow_validation_summary.json` (on disk, generated 2026-07-05T18:30:46Z)

| Field | JSON (stale) | CSV SSOT (current) | Match? |
|-------|-------------:|-------------------:|:------:|
| `total_events` | 2550 | **2554** | **✗ stale (−4)** |
| `buy_blocked_by_tae` | 0 | **0** | **✓** |
| `buy_skipped_other_reason` | 2525 | **2529** | **✗ stale (−4)** |
| `buy_allowed` | 25 | **25** | **✓** |
| `outcome_tracking_status` | `PENDING_NEXT_PHASE` | (0 blocked) | **✓** |
| `outcome_attribution.eligible_blocked_events` | 0 | **0** | **✓** |

**Cause:** Append-only ledger grew by **4 rows** (all skips) after summary was last written. Re-run `tae_shadow_validation_report.py` to sync.

### Fresh in-memory summary (same validation session, no file write)

| Field | Value |
|-------|------:|
| `total_events` | 2554 |
| `buy_blocked_by_tae` | 0 |
| `buy_skipped_other_reason` | 2529 |
| `buy_allowed` | 25 |

**Confirms:** Report builder logic matches CSV when run against current file.

### `TAE_X10_CHECKPOINT_VALIDATION_REPORT.md`

| Claim | Checkpoint doc | CSV SSOT | Match? |
|-------|---------------:|---------:|:------:|
| Total events | 2550 | **2554** | **✗ stale doc** |
| `buy_skipped_other_reason` | 2525 | **2529** | **✗ stale doc** |
| `buy_blocked_by_tae` | 0 | **0** | **✓** |
| `eligible_events` | 0 | **0** | **✓** |
| `PENDING_NEXT_PHASE` | yes | yes (0 blocked) | **✓** |
| Skips not attributed | yes | yes | **✓** |

Checkpoint report captured state at batch time (~18:30 UTC); CSV continued to receive bot cycles.

---

## 9. Mismatch summary

| Issue | Severity | Explanation |
|-------|----------|-------------|
| Summary JSON `total_events` 2550 vs CSV 2554 | **Low — staleness** | Ledger append-only; refresh summary batch |
| Checkpoint doc counts 2550 / 2525 | **Low — staleness** | Document snapshot before latest skips |
| `eligible_events` / blocked count | **None** | 0 = 0 across all sources |
| Skip rows entering attribution | **None** | Code + runtime verified |
| Wrong event types in CSV | **None** | Only 2 types present; blocked type absent |

**No X.10 filtering or scope defect identified.**

---

## 10. Interpretation

1. **CSV proves X.8 has not blocked any BUY in the logged history** — 0 `BUY_BLOCKED_BY_TAE` rows despite 2529 skip rows (session filter / max positions are **not** X.8 outcomes).

2. **X.10 correctly returns `eligible_events: 0` and `PENDING_NEXT_PHASE`** — empty blocked cohort is expected, not failure.

3. **Generated JSON/report counts for total/skipped rows lag live CSV** until batch refresh; blocked/eligible counts remain aligned.

4. **When `RISK_ADVISORY` first fires**, expect new rows with:
   - `event_type = BUY_BLOCKED_BY_TAE`
   - `block_new_buy = true`
   - `block_reason` containing `TAE RISK_ADVISORY`

---

## 11. Recommended refresh (no code change)

```bash
python3 tae_shadow_outcome_capture.py
python3 tae_shadow_validation_report.py
```

Then reconcile `total_events` / skip counts against CSV row count.

---

**Stop before commit** — no git commit created.

*End of TAE_X10_CSV_SSOT_VALIDATION.md*
