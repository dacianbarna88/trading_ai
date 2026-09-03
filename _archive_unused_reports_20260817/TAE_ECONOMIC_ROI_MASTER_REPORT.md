# TAE Economic ROI Master Report

**Generated:** 2026-07-15  
**Mode:** PAPER_ONLY · Construction **FROZEN**  
**Objective:** Maximize verified paper profit  
**Verdict:** `ECONOMIC_HIGHEST_ROI_IDENTIFIED`  
**Commit:** **NO** — identification only; no change implemented this sprint

Machine-readable twin: `tae_economic_roi_master_report.json`

---

## Portfolio economic baseline (existing SSOT)

| Metric | Value |
|--------|------:|
| Account value | $29,810.64 |
| Cash | $13,339.83 |
| Realized PnL | −$694.28 |
| Unrealized PnL | +$163.99 |
| Profit vs $30,000 base | −$189.36 |
| GII opportunity cost | $829.72 |
| Profit capture rate | 29.12% |
| MTM drawdown | ~1.75% |

---

## Ranking method

Evidence only from existing artifacts (portfolio, MTM, PTA, GII, ledger, capital challengers, attribution, DPE eval, decision replay + promotion audit, blocker ROI, orders).

Ranked by **unrealized economic value that can be converted on existing infrastructure without weakening Hard Risk / Decision State / Profit Integrity**.

Non-reproducible shadow claims stay visible but are **rejected for implementation priority**.

---

## TOP 10 subsystems (economic)

### 1. Profit Target Adapter → REDUCE trim sizing — HIGHEST UNREALIZED ROI

| Question | Answer |
|----------|--------|
| Money generated | **+$3.95** on HSBA REDUCE (observed) |
| Losses prevented | Not separately metered |
| Still unrealized / stops before capital | **~$617** HSBA notional: PTA asks **50%** trim; execution hardcoded **20%** |
| Upside if fully wired (existing infra) | Lock ~**$5.93** current HSBA UPNL immediately; free ~**$618** capital; historical missed context **$235.96** (bounded forward range **$6–$236**) |

**Gap:** `tae_profit_target_adapter.json` already emits `suggested_partial_size_pct`; PDE already biases scores via `apply_profit_target_adapter_bias`. **`tae_paper_execution.py` ignores size** (`trim_pct = 30 if conf<0.7 else 20`).

### 2. Learning-to-Profit Capital Challengers

| Question | Answer |
|----------|--------|
| Money generated | **+$30.35** challenger realized (4 REDUCE fills); realized −$724.62 → −$694.28 |
| Losses prevented | Indirect (capital freed to cash) |
| Unrealized / stopped before alloc | ~**$45** remaining PROMISING expected ex Hard Risk; **~$85** MU/AMAT/PROT blocked by Hard Risk |
| Upside if fully wired | Observe/scale **PROMOTED_CANDIDATE** only (HSBA, AAPL, PG); **do not** open MU/AMAT |

### 3. Opportunity Cost Ledger + GII

| Question | Answer |
|----------|--------|
| Money generated | $0 (meter only) |
| Losses prevented | $0 |
| Unrealized | **$829.72** measured ($685.08 CRITICAL) |
| Upside if wired | ~**$380** ex-MU/AMAT; remainder is Hard Risk territory |

### 4. Decision Replay / Shadow Trailing Protection

| Question | Answer |
|----------|--------|
| Money generated | $0 |
| Losses prevented | $0 on PAPER from the $5k claim |
| Unrealized (claimed) | **$5,138.54** protection Δ vs HOLD |
| Upside if wired | **REJECT** — `REPLAY_VALUE_NOT_REPRODUCIBLE`; PAPER-linked **$181.35** only |

### 5. Hard Risk Governor

| Question | Answer |
|----------|--------|
| Money generated | $0 |
| Losses prevented | Prevents CRITICAL MU/AMAT capital moves; DD context better under collaborative arm |
| Unrealized | $0 (protective, fully wired) |
| Upside | **Do not weaken** — blocked PROMISING is not free profit |

### 6. DPE Collaborative Philosophy

| Question | Answer |
|----------|--------|
| Money generated | Arm total_pnl **+$27.94** (normalized DPE capital); PF **1.1024** |
| Losses prevented | ~**$47.6** vs competitive realized gap |
| Unrealized | Already preferred winner |
| Upside | Maintain; LTB-DPE-PHIL-001 observed **−$0.32** → REVERT_OR_RETIRE |

### 7. Missed Profit Protection / Confidence Rules

| Question | Answer |
|----------|--------|
| Money generated | Attribution **+$123.09** (co-fired; not exclusive) |
| Losses prevented | Unknown |
| Unrealized | Already wired — often ends in PROTECT-only (`is_trade=false`) |
| Upside | Prefer **REDUCE** when PTA CRITICAL (no new module) |

### 8. Adaptive Paper Weights + Experiment consumption

| Question | Answer |
|----------|--------|
| Money generated | Shares credit with challenger **+$30.35** |
| Losses prevented | Capped deltas |
| Unrealized | Prior uniform-boost gap closed |
| Upside | Observe lag-1 learning; no architecture change |

### 9. Profit Protection Shadow / TRAIL_SHADOW

| Question | Answer |
|----------|--------|
| Money generated | AAPL path attribution **+$95.81** (position UPNL) |
| Losses prevented | Partial (same_action avoided **$18** in blocker study) |
| Unrealized | Book UPNL **+$163.99** |
| Upside | Align TRAIL protect-only with PTA size-driven REDUCE |

### 10. Execution `same_action` blocker

| Question | Answer |
|----------|--------|
| Money generated | $0 |
| Losses prevented | **$18** (blocker ROI) |
| Unrealized | Prior challenger **$0** profit delta |
| Upside | **REJECT** — `BLOCKER_REJECTED` |

---

## Single highest-ROI change

**ID:** `PTA_PARTIAL_SIZE_TO_REDUCE_TRIM`

**Change:** For REDUCE_PAPER, set `trim_pct` from existing PTA `suggested_partial_size_pct` when urgency ∈ {CRITICAL, HIGH} or strategy ∈ {REDUCE_EXPOSURE_SHADOW, TIGHTEN_TRAIL_SHADOW, PROTECT_PROFIT_SHADOW}; else keep current 20/30 heuristic.

| Constraint | Status |
|------------|--------|
| Reuses existing code | Yes — PTA JSON + REDUCE path |
| Smallest modification | Yes — one sizing branch |
| Highest expected return | Yes — HSBA alone ~$618 capital / $6–$236 bounded economic |
| Hard Risk | Unchanged |
| Decision State | Unchanged |
| Profit Integrity | Unchanged |

**Promotion criteria this sprint**

| Gate | Result |
|------|--------|
| Gain reproducible | Partial (20% trim already +$3.95; 50% is forward) |
| Sample size sufficient | **NO** (n=1 HSBA REDUCE) |
| Drawdown increases | Not expected (cut COLLAPSED) |
| Hard Risk weakens | No |
| **Implement / commit** | **NO** — frozen + sample gate |

---

## Explicitly rejected for profit action

1. Wire Decision Replay $5,138 claim → `REPLAY_VALUE_NOT_REPRODUCIBLE`
2. Relax `same_action` → already `$0` uplift
3. Capitalize MU/AMAT PROMISING → Hard Risk CRITICAL
4. Profit Edge Discovery → `NO_EDGE_FOUND`

---

## Final verdict

```
ECONOMIC_HIGHEST_ROI_IDENTIFIED
```
