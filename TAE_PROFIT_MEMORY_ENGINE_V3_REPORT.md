# TAE Profit Memory Engine v3 — Implementation Report

**Date:** 2026-07-06  
**Checkpoint:** ea84ad2 — TAE PIB V2  
**Mode:** SHADOW_ONLY · NO_BROKER · NO_LIVE_EXECUTION_CHANGE  
**Status:** **PASS** (includes deduplication fix)

---

## Summary

Built `tae_profit_memory_engine.py` — a shadow-only historical memory layer that captures profit episodes from PIB and protection shadow outputs, classifies outcomes, aggregates per-ticker memory, and persists append-only history.

PIB logic was **not modified** (memory engine is standalone; integration deferred).

---

## Deduplication Fix (v3.1)

### Problem

Prior fingerprint included `captured_at`, so back-to-back runs (e.g. 14:01 and 14:02) appended identical episodes.

### Solution

Stable `episode_key` (timestamp-independent):

```
{ticker}|{high_pct}|{current_pct}|{missed_usd}|{pib_recommendation}|{psp_urgency}
```

- Stored on every episode
- Append skips if key already exists
- Legacy duplicates collapsed on load (keeps earliest `captured_at`)
- Aggregates use **unique episodes only**

### Validation (post-fix)

| Run | Raw before | Unique | Added | Skipped | Ignored in aggregation |
|-----|------------|--------|-------|---------|------------------------|
| 1 | 24 → 12 | 12 | 0 | 12 | 12 (legacy collapsed) |
| 2 | 12 | 12 | 0 | 12 | 0 |

Ticker observations remain **1** per ticker — no false inflation.

---

## Memory Model

### Profit episode (captured per run)

| Field | Source |
|-------|--------|
| `ticker` | PIB / shadow position |
| `current_pct`, `high_pct`, `drawdown`, `missed_usd` | PIB + shadow merge |
| `pib_recommendation` | PSP-adjusted or PIB v1 rec |
| `psp_survival_probability`, `psp_giveback_risk`, `psp_urgency` | PIB v2 |
| `memory_label` | Classification engine |
| `episode_key` | Stable dedupe key (no timestamp) |
| `captured_at` | Run timestamp |

### Classification rules (priority order)

| Label | Rule |
|-------|------|
| `PROFIT_COLLAPSED` | `high_pct >= 6` and `current_pct <= 1` |
| `PROFIT_DECAYED` | `high_pct >= 4` and `drawdown <= -2` |
| `PROFIT_SURVIVED` | `current_pct >= high_pct × 0.75` and `current_pct > 0` |
| `UNKNOWN_OUTCOME` | otherwise |

### Per-ticker memory bias

| Bias | Rule |
|------|------|
| `MEMORY_PROTECT_EARLY` | `collapse_rate + decay_rate >= 0.60` and `observations >= 3` |
| `MEMORY_HOLD_WINNERS` | `survival_rate >= 0.60` and `observations >= 3` |
| `MEMORY_NEUTRAL` | else (including `< 3` observations) |

### Persistence

- **Initialize** empty store on first run
- **Append** new episodes on each run (dedupe by `episode_key`)
- **Collapse** legacy duplicates on load
- **Aggregate** from unique episodes only
- Prior unique episodes preserved across runs

### Global verdicts

| Verdict | Condition |
|---------|-----------|
| `MEMORY_READY_FOR_OBSERVATION` | ≥10 episodes, ≥3 tickers |
| `MEMORY_NEEDS_MORE_DATA` | ≥1 episode, below threshold |
| `MEMORY_NOT_READY` | No sources or zero episodes |

---

## Files Created

| File | Purpose |
|------|---------|
| `tae_profit_memory_engine.py` | Memory capture, classify, persist |
| `tae_profit_memory_engine.json` | Historical episode store + ticker aggregates |
| `tae_profit_memory_engine.md` | Human-readable memory report |
| `TAE_PROFIT_MEMORY_ENGINE_V3_REPORT.md` | This report |

**Not modified:** `live_bot.py`, `core/trades.py`, `portfolio.csv`, `tae_profit_intelligence_brain.py`, broker/execution.

---

## Validation Output

### Command

```bash
python3 tae_profit_memory_engine.py
```

### Run 1 (initialize)

```
===== TAE PROFIT MEMORY ENGINE v3 =====
Final verdict: MEMORY_READY_FOR_OBSERVATION
Total episodes: 12
Tickers tracked: 12
Added this run: 12
Duplicates skipped: 0
Top collapse ticker: HSBA.L (collapse+decay=1.00)
```

### Run 2 (dedupe test — post-fix)

```
Added this run: 0
Duplicates skipped: 12
Duplicates ignored in aggregation: 0
Unique episodes: 12 (unchanged)
```

Duplicate protection confirmed — immediate re-runs add zero episodes; ticker obs stay at 1.

### Artifact checks

| Check | Result |
|-------|--------|
| `tae_profit_memory_engine.json` | **EXISTS** |
| `tae_profit_memory_engine.md` | **EXISTS** |
| `live_bot.py` changed | **NO** |
| `core/trades.py` changed | **NO** |
| `portfolio.csv` changed | **NO** |
| PIB modified | **NO** |

---

## Sample Ticker Memory

### HSBA.L — PROFIT_COLLAPSED

```json
{
  "ticker": "HSBA.L",
  "observations": 1,
  "collapsed_count": 1,
  "collapse_rate": 1.0,
  "survival_rate": 0.0,
  "total_missed_usd": 235.96,
  "recommended_memory_bias": "MEMORY_NEUTRAL"
}
```

Episode: high +9.22%, current −0.22%, PIB=WATCH, PSP urgency CRITICAL.

### PM — PROFIT_SURVIVED

```json
{
  "ticker": "PM",
  "observations": 1,
  "survived_count": 1,
  "survival_rate": 1.0,
  "recommended_memory_bias": "MEMORY_NEUTRAL"
}
```

Episode: high +3.56%, current +2.67% (≥75% retention), PIB=HOLD.

### MU / AMAT — PROFIT_COLLAPSED

Peak ≥6%, current ≤1% — collapse label; bias remains NEUTRAL until ≥3 observations accumulate.

---

## Global Summary (current run)

| Metric | Value |
|--------|-------|
| Total episodes | 12 |
| Tickers tracked | 12 |
| Collapsed episodes | 3 (HSBA.L, MU, AMAT) |
| Survived episodes | 3 (PM, PG, MRK) |
| Final verdict | `MEMORY_READY_FOR_OBSERVATION` |

**Top collapse:** HSBA.L, MU, AMAT  
**Top survival:** PM, PG, MRK  

Bias signals (`MEMORY_PROTECT_EARLY` / `MEMORY_HOLD_WINNERS`) activate after ≥3 observations per ticker — currently all `MEMORY_NEUTRAL` on first capture.

---

## Live Execution Confirmation

| Check | Status |
|-------|--------|
| BUY/SELL executed | **NO** |
| `live_trading_impact` | `NONE` |
| `mode` | `SHADOW_ONLY` |
| Portfolio writes | **NO** |

---

## Overall Verdict

**PASS** — Profit Memory Engine v3 implemented, validated, persistence and dedupe confirmed. Live trading unchanged. PIB integration deferred per sprint scope.
