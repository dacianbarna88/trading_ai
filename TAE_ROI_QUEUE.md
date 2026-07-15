# TAE ROI Queue

**Generated:** 2026-07-15  
**Version:** 2.0 (economic orchestration closure)  
**Mode:** PAPER_ONLY · Construction / Architecture / Constitution **FROZEN**  
**Machine SSOT:** `tae_roi_queue.json`  
**Next dollar:** `TAE_NEXT_DOLLAR.md` / `tae_next_dollar.json`  
**Orchestration:** `run_roi_economic_orchestration()` in `tae_roi001_challenger.py` — hooked from `full-paper-cycle`

---

## Rule Zero

Never ask what can be built.  
Ask: **what existing capability produces the next verified dollar?**

Only **queue_rank #1** may be worked. On completion → **recalculate the entire queue**.

---

## ROI_SCORE

```
ROI_SCORE = (Estimated_upside_$ × conf × sample_f × replay_f × readiness_mult × observed_bonus)
            / complexity
```

| Factor | Rule |
|--------|------|
| conf | HIGH 0.85 · MED 0.55 · LOW 0.30 · REJECT 0 |
| sample_f | max(0.25, min(1, n/5)) |
| replay_f | YES → 1.0 · NO → 0.25 |
| readiness_mult | CHALLENGER_ONLY 1.0 · PROMOTE_READY 1.15 · NOT_READY 0.35 · LOW_PRIORITY 0.25 · REJECTED/FORBIDDEN 0 |
| observed_bonus | 1.25 if path already booked verified PnL > 0 |
| gates | Hard Risk / Decision State / Profit Integrity must be YES else score = 0 |

**Money definition:** `Estimated_upside_usd` is conservative **profit-adjacent** dollars — not capital notional freed.

---

## Promotion policy

Promote only if **any** of: higher realized profit · lower drawdown · higher profit factor · higher expectancy  
**and** no regression in: Hard Risk · Decision State · Profit Integrity · Reconciliation.

| Failure | Action |
|---------|--------|
| ROI not demonstrable | REJECT |
| Replay fails | REJECT |
| Sample insufficient | **CHALLENGER_ONLY** |

---

## Queue (sorted by ROI_SCORE)

| Rank | ROI_ID | Subsystem | Upside $ | Conf | n | Replay | Capital | Risk | HR | DS | PI | Cx | Replay time | Readiness | ROI_SCORE |
|:----:|--------|-----------|--------:|:----:|--:|:------:|--------:|------|:--:|:--:|:--:|---:|:----------:|-----------|----------:|
| **1** | **ROI-001** | **PTA → REDUCE trim sizing** | **29.53** | MED | 1 | YES | 0 | ↓ DD (COLLAPSED) | Y | Y | Y | 2 | 15-30m | **CHALLENGER_ONLY** | **2.5377** |
| 2 | ROI-002 | HSBA PROMOTED residual | 17.73 | MED | 1 | YES | 0 | ↓ collapsed | Y | Y | Y | 3 | 20-40m | CHALLENGER_ONLY | 1.0158 |
| 3 | ROI-009 | MPP → REDUCE if PTA CRITICAL | 3.91 | MED | 12 | YES | 0 | bookkeeping→trade | Y | Y | Y | 4 | 30-60m | CHALLENGER_ONLY | 0.5376 |
| 4 | ROI-007 | Replay PAPER-linked residual | 27.20 | LOW | 23 | YES | 0 | more exits | Y | Y | Y | 6 | 60-120m | NOT_READY | 0.4760 |
| 5 | ROI-006 | Ledger → PDE bias (ex HR) | 19.03 | LOW | 12 | YES | 0 | exit pressure | Y | Y | Y | 5 | 45-90m | NOT_READY | 0.3996 |
| 6 | ROI-005 | AAPL PROMOTED residual | 4.79 | LOW | 1 | YES | 0 | trims winner | Y | Y | Y | 3 | 20-40m | CHALLENGER_ONLY | 0.1497 |
| 7 | ROI-008 | Same-cycle weight reorder | 4.55 | LOW | 4 | YES | 0 | faster learn | Y | Y | Y | 4 | 30-60m | NOT_READY | 0.0955 |
| 8 | ROI-004 | KEEP_GROWING reduce guard | 1.58 | MED | 1 | YES | 0 | protect winners | Y | Y | Y | 3 | 20-40m | CHALLENGER_ONLY | 0.0724 |
| 9 | ROI-003 | QQQ CRITICAL REDUCE | 1.89 | LOW | 0 | YES | 0 | cut small loss | Y | Y | Y | 3 | 15-30m | CHALLENGER_ONLY | 0.0472 |
| 10 | ROI-010 | DPE arm metrics depth | 4.18 | LOW | — | YES | 0 | neutral | Y | Y | Y | 5 | 45-90m | LOW_PRIORITY | 0.0157 |
| 11 | ROI-013 | GE challenger retire | 0.05 | HIGH | 1 | YES | 0 | stop −edge | Y | Y | Y | 1 | 10m | CHALLENGER_ONLY | 0.0106 |

### Parked (ROI_SCORE = 0)

| ROI_ID | Subsystem | Why |
|--------|-----------|-----|
| ROI-014 | Claimed $5,138 replay promotion | REPLAY_VALUE_NOT_REPRODUCIBLE |
| ROI-012 | MU/AMAT PROMISING capital | Hard Risk CRITICAL — FORBIDDEN |
| ROI-016 | policy_skip relaxation | Likely weakens HR — FORBIDDEN |
| ROI-011 | same_action retry | Prior BLOCKER_REJECTED ($0) |
| ROI-015 | Profit Edge Discovery | NO_EDGE_FOUND |

---

## Economic lifecycle (SSOT fields)

Each queue entry carries orchestration state — **not** capital-challenger or DPE status:

| Field | Purpose |
|-------|---------|
| `status` | `WAITING` · `ACTIVE_CHALLENGER` · `ECONOMICALLY_POSITIVE` · `PROMOTED_PAPER` · `REJECTED` · `RETIRED` · `WAITING_IMPLEMENTATION_MAPPING` |
| `active` | Exactly **one** `true` at a time |
| `production_enabled` | Drives `roi001_challenger` flag in `run_paper_execution()` |
| `sample_size` / `minimum_sample_size` | Auto-refreshed each cycle from order history |
| `*_delta` metrics | Baseline vs challenger economics |
| `depends_on` | Queue gating (ROI-002 waits for ROI-001 terminal) |

**Enforcement:** `ensure_single_active_roi()` — conflict → `BLOCKED_BY_ROI_STATE_CONFLICT`.

## Work rule

```
ACTIVE WORK = single active ROI only (currently ROI-001)
Evidence refresh = automatic each full-paper-cycle
Production sizing = PROMOTED_PAPER only
On terminal completion → advance queue + rebuild tae_next_dollar.json
```

## Current active ROI (2026-07-15)

| Field | Value |
|-------|-------|
| ROI_ID | **ROI-001** |
| Status | **ECONOMICALLY_POSITIVE** |
| Sample | **4 / 10** |
| Production | **false** (baseline trim remains) |
| Realized Δ | +$11.92 |
| Next waiting | ROI-002 |

---

## Verdict

```
ECONOMIC_ORCHESTRATION_CLOSED
NEXT_DOLLAR_IDENTIFIED (ROI-001 active)
```
