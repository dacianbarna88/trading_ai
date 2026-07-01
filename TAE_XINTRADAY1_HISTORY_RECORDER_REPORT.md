# TAE X.INTRADAY-1 — Daily Fade History Recorder Report

**Date:** 2026-07-01  
**Sprint:** X.INTRADAY-1  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Status:** Implemented — `live_bot.py` unchanged

---

## 1. Problem observed

Repeated intraday fade intelligence runs confirmed a persistent pattern:

| Date | Missed intraday opportunity |
|------|----------------------------|
| 2026-06-30 | ~366 USD |
| 2026-07-01 | ~461 USD |

Single-run JSON/MD snapshots are useful but **not cumulative**. TAE cannot learn statistically (top fade tickers, shadow strategy comparison, classification frequency) without a persistent history.

---

## 2. Design implemented

### Architecture

```
tae_intraday_fade_intelligence.py
        │
        │ build_report() → write_outputs()
        ▼
tae_intraday_fade_history.record_fade_report()
        │
        ├── append runtime_outputs/tae_intraday_fade_history.csv
        ├── append runtime_outputs/tae_intraday_fade_history.json
        ├── append runtime_outputs/tae_intraday_fade_daily_summary.json
        └── (standalone) tae_intraday_fade_history.py → tae_intraday_fade_history_summary.md
```

### Per-ticker record fields

`date`, `timestamp`, `run_id`, `ticker`, `shares`, `avg_price`, `open`, `high`, `low`, `current`, `current_pct`, `high_pct`, `low_pct`, `missed_opportunity_usd`, `drawdown_from_high_pct`, `classification`, `shadow_sell_20`, `shadow_sell_30`, `shadow_trailing_1`, `shadow_trailing_1_5`

### Daily summary fields

`date`, `timestamp`, `run_id`, totals (current / high / missed / shadow), classification counts (`num_hold`, `num_watch_intraday_fade`, `num_significant_intraday_fade`, `num_potential_partial_take_profit`, `num_risk_intraday_low`), `verdict`

### Duplicate protection

- **Same `run_id`:** entire run skipped (no duplicate append)
- **Same ticker within run:** one row kept (dedupe by ticker)
- **Multiple runs per day:** allowed — each unique `run_id` appends

`run_id` defaults to normalized `generated_at` from the intelligence report.

### Aggregate summary (`tae_intraday_fade_history.py`)

Produces:

- Top tickers by total missed opportunity
- Top tickers by `SIGNIFICANT_INTRADAY_FADE` count
- Average missed opportunity per ticker
- Best shadow strategy (cumulative across daily summaries)
- Number of observations
- Number of days observed

---

## 3. Files created / modified

| File | Action |
|------|--------|
| `tae_intraday_fade_history.py` | **Created** — recorder + aggregate summary |
| `tae_intraday_fade_history_test.py` | **Created** — 8 unit tests |
| `TAE_XINTRADAY1_HISTORY_RECORDER_REPORT.md` | **Created** — this report |
| `tae_intraday_fade_intelligence.py` | **Modified** — calls `record_fade_report()` after `write_outputs()` |

**Not modified:** `live_bot.py`, `core/market_data_layer.py`, BUY/SELL/Risk/Broker/Trailing, thresholds.

---

## 4. Tests run

```bash
python3 -m py_compile tae_intraday_fade_history.py tae_intraday_fade_intelligence.py
python3 tae_intraday_fade_history_test.py
python3 tae_intraday_fade_intelligence_test.py
python3 tae_intraday_fade_intelligence.py
python3 tae_intraday_fade_history.py
git status --short
```

| Test module | Coverage |
|-------------|----------|
| `tae_intraday_fade_history_test.py` | append CSV/JSON, duplicate `run_id`, dedupe ticker, daily summary, top missed, classification counts, best shadow strategy |
| `tae_intraday_fade_intelligence_test.py` | existing FIFO / classification / shadow math (unchanged) |

---

## 5. Outputs generated

| Path | Description |
|------|-------------|
| `runtime_outputs/tae_intraday_fade_history.csv` | Flat history (all runs) |
| `runtime_outputs/tae_intraday_fade_history.json` | Structured position records |
| `runtime_outputs/tae_intraday_fade_daily_summary.json` | One summary row per run |
| `tae_intraday_fade_history_summary.md` | Human-readable aggregate stats |

Intelligence module continues to write:

- `tae_intraday_fade_intelligence.json`
- `tae_intraday_fade_intelligence.md`

---

## 6. Confirmations

| Check | Status |
|-------|--------|
| SHADOW_ONLY | **YES** |
| PAPER_ONLY | **YES** |
| NO_BROKER | **YES** |
| `live_bot.py` untouched | **YES** |
| Market Data Layer untouched | **YES** |
| Thresholds unchanged | **YES** |
| Git commit | **NO** (per request) |

---

## 7. Recommendations for X.INTRADAY-2 Learning Engine

After 5–10 days of history:

1. **Ticker fade score** — rolling avg missed opportunity + fade frequency per symbol
2. **Shadow strategy backtest** — compare sell-20 vs sell-30 vs trailing on historical runs
3. **Threshold calibration** — tune `SIGNIFICANT_MISSED_USD` / `high_pct` from empirical distribution
4. **Time-of-day fade curve** — if future runs capture intraday timestamps, model when fades typically occur
5. **Dashboard panel** — render `tae_intraday_fade_history_summary.md` metrics in command center
6. **Promotion gate** — only propose live partial-TP after Learning Engine shows net improvement vs hold baseline

All X.INTRADAY-2 work should remain paper/shadow until explicit sprint approval.

---

*TAE X.INTRADAY-1 — persistent fade history for statistical learning.*
