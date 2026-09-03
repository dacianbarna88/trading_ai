# TAE DPE Blocked Job Report

**Date:** 2026-07-07  
**Mode:** READ_ONLY · NO_BROKER · NO_EXECUTION · NO_LIVE_CHANGE · NO_COMMIT  
**Source:** `runtime_outputs/dpe/execution_jobs.jsonl` (read-only audit)

---

## Executive summary

| Metric | Value |
|--------|-------|
| Total BLOCKED lines in JSONL | **38** |
| Unique blocked `job_id` | **8** |
| Duplicate blocked lines (re-split runs) | **30** |
| Blocking reason (all) | `COLLAPSE_RISK` |
| Affected ticker | **HSBA.L only** |
| Valid blocked | **8 / 8 unique jobs (100%)** |
| Invalid blocked | **0** |

**Verdict:** All blocked jobs are **expected and correct**. No splitter defect. Duplicates are append-only re-run artifacts, not invalid blocks.

---

## How blocking works (DPE-2)

From `tae_execution_splitter.py` → `job_status()`:

| Condition | Status |
|-----------|--------|
| Event invalid | `INVALID` |
| COMPETITIVE + `philosophy_preference == AVOID` | `BLOCKED` |
| COLLABORATIVE + `philosophy_preference == AVOID` + `REDUCE` in growth strategy | `BLOCKED` |
| `portfolio_verdict == PORTFOLIO_CRITICAL` | `BLOCKED` |
| Missing snapshot data | `QUEUED` |
| Otherwise | `READY` |

`decision_reason` is informational via `infer_decision_reason()` — `COLLAPSE_RISK` when `collapse_probability >= 0.5`.

---

## Aggregate counts

### By status (full JSONL)

| Status | Count |
|--------|------:|
| READY | 360 |
| BLOCKED | 38 |
| BLOCKED unique job_ids | 8 |

### By blocking reason

| Reason | Lines | Unique jobs | Expected? |
|--------|------:|------------:|-----------|
| `COLLAPSE_RISK` | 38 | 8 | ✅ Yes |

### By executor

| Executor | BLOCKED lines |
|----------|--------------:|
| COMPETITIVE | 19 |
| COLLABORATIVE | 19 |

Symmetric blocking per ticker event (one job per arm per split).

### By ticker

| Ticker | BLOCKED lines | Unique jobs |
|--------|--------------:|------------:|
| HSBA.L | 38 | 8 |

No other tickers are blocked.

---

## Per-job analysis (unique blocked jobs)

All 8 unique blocked jobs share the same profile:

| Field | Value |
|-------|-------|
| Ticker | HSBA.L |
| `decision_reason` | COLLAPSE_RISK |
| `action_candidate` | REDUCE |
| `collapse_probability` | 1.0 |
| `philosophy_preference` | AVOID |
| `lifecycle_stage` | COLLAPSED |
| Growth score | ~3.4 (low) |

### Why COMPETITIVE is blocked

- `philosophy_preference == AVOID` → competitive arm must not act.

### Why COLLABORATIVE is blocked

- `philosophy_preference == AVOID` **and** growth strategy contains `REDUCE` → collaborative arm also blocked.

### Why reason is `COLLAPSE_RISK`

- `collapse_probability = 1.0` (≥ 0.5 threshold) → `infer_decision_reason()` returns `COLLAPSE_RISK`.

**Classification:** ✅ **Expected / valid**

---

## Expected vs unexpected

| Category | Count | Notes |
|----------|------:|-------|
| **Expected blocked** | 8 unique / 38 lines | HSBA.L collapse + AVOID philosophy |
| **Unexpected blocked** | 0 | No wrong ticker, no missing context, no INVALID masquerading as BLOCKED |
| **Duplicate lines** | 30 | Same `job_id` re-appended across splitter runs — idempotency at executor layer, not jsonl dedup |

### Expected block triggers observed

1. High collapse probability on collapsed lifecycle ticker
2. Philosophy lab `AVOID` preference on HSBA.L
3. `REDUCE_EXPOSURE_SHADOW` strategy candidate
4. PORTFOLIO_HIGH_RISK context (does not alone block — philosophy + strategy rules apply)

### Unexpected patterns checked — none found

- ❌ BLOCKED without `decision_reason`
- ❌ BLOCKED on PORTFOLIO aggregate jobs
- ❌ BLOCKED with `philosophy_preference` missing
- ❌ BLOCKED on high-growth tickers (MRK, PM, SPY)
- ❌ `PORTFOLIO_CRITICAL` blocks (verdict is `PORTFOLIO_HIGH_RISK`, not CRITICAL)

---

## Duplicate lines explanation

The JSONL contains **38 BLOCKED lines** but only **8 unique `job_id` values**. The extra 30 lines come from **multiple splitter runs** appending the same logical jobs (append-only log). Paper executors dedupe via `processed_job_ids` — blocked jobs are never executed.

**Not a defect.** Optional hygiene: compact or mark duplicate job_ids in a future read-only audit view.

---

## Recommendations

### P0 — No action required

1. **Accept all 8 unique HSBA.L blocks** — correct protective behavior for collapsed ticker with AVOID philosophy.
2. **Do not force-READY** blocked jobs — would violate DPE-2 safety rules.
3. **Do not modify** `tae_execution_splitter.py` blocking logic.

### P1 — Operational clarity (optional)

1. Morning audit may report **unique blocked count (8)** alongside JSONL line count (38) to avoid confusion.
2. When HSBA.L lifecycle recovers (collapse_probability < 0.5, philosophy shifts from AVOID), re-run `dpe-splitter` — jobs should become READY automatically.

### P2 — Queue hygiene (optional, non-urgent)

1. Add read-only dedup summary to splitter report (`unique_blocked_job_ids`).
2. Document append-only JSONL duplication in DPE foundation docs.

---

## Impact on paper executors

| Arm | READY jobs | BLOCKED (unique) | Effect |
|-----|----------:|-----------------:|--------|
| COMPETITIVE | 180 lines | 4 unique HSBA.L | HSBA.L skipped |
| COLLABORATIVE | 180 lines | 4 unique HSBA.L | HSBA.L skipped |

Remaining READY jobs process normally. No live portfolio impact.

---

## Safety confirmation

| Rule | Status |
|------|--------|
| READ_ONLY audit | ✅ |
| NO_BROKER | ✅ |
| NO_DPE_LOGIC_CHANGE | ✅ |
| NO_LIVE_CHANGE | ✅ |
| NO_COMMIT | ✅ |

---

## Sign-off

| Question | Answer |
|----------|--------|
| Total blocked | 38 lines / 8 unique jobs |
| Valid blocked | **8 (100%)** |
| Invalid blocked | **0** |
| Understood? | **Yes** |
| Action required? | **No** |
