# TAE X.INTRADAY-2 — Intraday Discovery & Learning Engine Report

**Date:** 2026-07-01  
**Sprint:** X.INTRADAY-2  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Status:** Implemented — `live_bot.py` unchanged

---

## 1. Objective

X.INTRADAY-1 persistă istoricul fade intraday. X.INTRADAY-2 **învață din acel istoric** — agregă metrici per ticker, per clasificare, per zi, descoperă pattern-uri recurente și emite recomandări **doar de cercetare** (fără BUY/SELL live).

---

## 2. Inputs

| File | Content |
|------|---------|
| `runtime_outputs/tae_intraday_fade_history.csv` | Per-ticker observations (all runs) |
| `runtime_outputs/tae_intraday_fade_daily_summary.json` | Daily portfolio totals + shadow strategy sums |

---

## 3. Outputs

| File | Content |
|------|---------|
| `tae_intraday_discovery_engine.json` | Full structured learning report |
| `tae_intraday_discovery_engine.md` | Human-readable summary |

---

## 4. What the engine computes

### Dataset health

- `observations`, `unique_days`, `unique_tickers`
- `data_quality`: GOOD / PARTIAL / POOR / EMPTY (based on DATA_UNAVAILABLE rate)
- `minimum_sample_warning`: true when observations < 30

### Ticker-level learning

Per ticker: observations, avg/total missed opportunity, significant fade count/rate, partial-TP count, risk-intraday-low count, avg current/high/drawdown %, best shadow strategy, confidence (LOW / MEDIUM / HIGH).

### Classification-level learning

Per classification: count, avg missed opportunity, avg current/high %, best shadow strategy.

### Daily-level learning

Per day: total missed, current unrealized, theoretical high, best shadow strategy, verdict.

### Pattern discovery

| Pattern type | Trigger (initial rules) |
|--------------|-------------------------|
| `LOW_CONFIDENCE_INSUFFICIENT_SAMPLE` | observations < 30 |
| `BEST_SHADOW_TRAILING` | cumulative trailing shadow PnL best globally |
| `BEST_SHADOW_PARTIAL_SELL` | cumulative partial-sell shadow PnL best globally |
| `REPEATED_SIGNIFICANT_FADE` | significant_fade_rate > 0.5, observations ≥ 3 |
| `REPEATED_RISK_INTRADAY_LOW` | risk_intraday_low_count ≥ 2, observations ≥ 3 |
| `HIGH_FADE_TICKER` | avg missed ≥ 50 USD or top-tier total missed |

Each pattern includes: `id`, `pattern_type`, `scope`, `subject`, `observations`, `metric`, `value`, `confidence`, `recommendation`.

### Recommendations (SHADOW_ONLY)

- `INSUFFICIENT_DATA`
- `PRIORITIZE_TRACKING`
- `TEST_TRAILING_SHADOW`
- `TEST_PARTIAL_SELL_SHADOW`
- `CONTINUE_OBSERVATION`

No live execution language. No BUY/SELL.

---

## 5. Tests

`tae_intraday_discovery_engine_test.py` validates:

- Dataset health
- Ticker aggregation
- Classification aggregation
- Best shadow strategy selection
- Confidence scoring (LOW / MEDIUM / HIGH)
- Insufficient sample warning
- Pattern generation
- Recommendations generation
- JSON/Markdown output

```bash
python3 -m py_compile tae_intraday_discovery_engine.py
python3 tae_intraday_discovery_engine_test.py
python3 tae_intraday_discovery_engine.py
```

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
| Git commit | **NO** |

---

## 7. Limitations

Current dataset is **small** (~14 observations, 2 days). Engine correctly flags `minimum_sample_warning` and emits `LOW_CONFIDENCE_INSUFFICIENT_SAMPLE`.

Reliable ticker-level confidence requires **30+ observations** per ticker ideally; portfolio-level learning needs **30+ total observations** before shadow strategy rankings stabilize.

Patterns with `confidence: LOW` should be treated as **hypotheses**, not trading rules.

---

## 8. Next: X.INTRADAY-3 Profit Protection Advisory

1. **Advisory layer** — translate discovery patterns into daily shadow advisories per open position
2. **Alert tiers** — WATCH / REVIEW / RESEARCH_ONLY based on pattern + confidence
3. **Dashboard panel** — render `tae_intraday_discovery_engine.json` in command center
4. **Paper simulation tracker** — track hypothetical partial/trailing outcomes vs actual hold
5. **Promotion gate** — only after 30+ days and consistent shadow outperformance propose live partial-TP sprint

All X.INTRADAY-3 work remains paper/shadow until explicit approval.

---

## 9. Files created

```
tae_intraday_discovery_engine.py
tae_intraday_discovery_engine_test.py
TAE_XINTRADAY2_DISCOVERY_ENGINE_REPORT.md
```

Runtime artifacts (on run):

```
tae_intraday_discovery_engine.json
tae_intraday_discovery_engine.md
```

---

*TAE X.INTRADAY-2 — pattern discovery from persistent intraday fade history.*
