# TAE Multi-Horizon Integration Audit

**Generated:** 2026-07-07  
**Mode:** READ_ONLY audit + minimal PAPER wiring  
**Verdict:** **HORIZON_GAPS_WIRED** — existing SSOT now consumed by learning-profit → paper-decisions → validation

---

## Executive summary

TAE has multi-horizon artifacts across **legacy txt/csv** (2Y–10Y regional backtest) and **research_core JSON** (2Y–20Y simulation validation). Before P0.3, horizons were **not consumed** by `learning-profit`, `paper-decisions`, or `paper-experiments`.

P0.3 wires **existing outputs only** (no new horizon engine) into:

| Consumer | Horizon wiring |
| --- | --- |
| `tae_learning_to_profit_bridge.py` | Hypotheses enriched with `horizon_context`, alignment, reason |
| `tae_paper_decision_engine.py` | Action scoring + decision fields for all 7 horizons |
| `tae_dpe_paper_executor_infra.py` | Validation results include horizon explanation |

**Not wired (by design — live/forbidden):** `live_bot.py`, `portfolio.csv`, `live_signals.csv`, broker execution, `core/`, `research_core/` runtime mutation.

---

## Horizon SSOT inventory

| Horizon | Primary source | Freshness | Pre-P0.3 consumer | Post-P0.3 consumer |
| --- | --- | --- | --- | --- |
| **7D** | `tae_intraday_fade_intelligence.json` + GII `current_pct` | ~3h / ~12h | profit context (indirect) | **paper-decisions**, LTP hypotheses |
| **1M** | `strategic_intelligence_summary.txt` (market proxy ETF) | ~163h | live allocation enricher | **paper-decisions**, LTP hypotheses |
| **1Y** | strategic 12M + `historical_intelligence.csv` 2Y/2 fallback | ~163h / ~334h | allocation enricher | **paper-decisions**, LTP hypotheses |
| **2Y** | `historical_intelligence.csv` | ~334h | strategic horizon (manual) | **paper-decisions**, LTP hypotheses |
| **5Y** | `historical_intelligence.csv` | ~334h | adaptive allocation | **paper-decisions**, LTP hypotheses |
| **10Y** | `historical_intelligence.csv` | ~334h | adaptive allocation | **paper-decisions**, LTP hypotheses |
| **20Y** | `historical_intelligence.csv` + `tae_historical_results_analysis.json` | ~334h / ~163h | research_core validation | **paper-decisions**, LTP hypotheses |

---

## Module audit matrix

| Module / artifact | Output | Freshness | learning-profit | paper-experiments | paper-decisions | DPE | Capital allocation | PAPER actions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `historical_intelligence.csv` | per-ticker 2Y–20Y returns | ~334h | **WIRED** (via LTP enrich) | indirect | **WIRED** | — | legacy manual | HOLD/SELL/ROTATE bias |
| `strategic_intelligence_summary.txt` | 1M/12M market ETF returns | ~163h | **WIRED** | — | **WIRED** | — | allocation enricher | BUY/HOLD gate |
| `horizon_vote_summary.txt` | LONG_TERM vote | ~163h | source ref | — | context ref | — | allocation runner | ROTATE context |
| `tae_intraday_fade_intelligence.json` | intraday position pct | ~3h | — | — | **WIRED** (7D proxy) | — | — | PROTECT/HOLD |
| `tae_cross_validation_report.json` | cross-horizon consistency | ~285h | — | — | backdrop score | — | governance | conflict flag |
| `tae_historical_results_analysis.json` | 2Y–20Y job cohorts | ~163h | — | experiment context | backdrop | DPE metrics (design) | — | long-term trend |
| `multi_horizon_backtest.csv` | US/EU/UK 2Y–10Y | ~334h | — | — | presence flag | — | adaptive allocation | — |
| `tae_strategic_allocation_runtime.json` | allocation orchestration | ~163h | — | — | — | — | **live advisory** (stale) | — |
| `research_core/validation/cross_regime_validator.py` | validation JSON | on demo run | — | — | — | — | promotion gate | — |
| `regime_intelligence_engine.py` | regime summary txt | varies | — | — | — | — | profit context | — |
| `core/market_regime.py` | SPY SMA200 | runtime | — | — | **NOT WIRED** (live) | — | live_bot BUY gate | live only |

---

## PAPER action impact (post-wiring)

| Action | Horizon rule |
| --- | --- |
| **BUY_PAPER** | Requires positive 7D + 1M alignment unless top-growth or PROMISING experiment override |
| **SELL_PAPER / REDUCE_PAPER** | Strengthened when short horizon weak vs positive long-term (5Y/10Y/20Y) |
| **HOLD_PAPER** | Strengthened when long-term positive and short weakness treated as pullback |
| **PROTECT_PAPER** | Strengthened when short drawdown ≥2.5% with intact long-term trend |
| **ROTATE_PAPER** | Strengthened when candidate `horizon_alignment_score` beats weakest held position |
| **SKIP_PAPER** | Boosted on horizon conflict or failed BUY alignment gate |

---

## Decision output fields (required — now present)

Each PAPER decision includes:

- `horizon_context` (7D, 1M, 1Y, 2Y, 5Y, 10Y, 20Y with trend + return_pct + source)
- `short_term_trend_7d`, `monthly_trend`, `yearly_trend`, `long_term_trend`
- `horizon_alignment_score`, `horizon_conflict_flag`, `horizon_reason`

Validation results (`decision_validation_results.json`) propagate `horizon_reason` into `reason` and `evidence_summary`.

---

## Orphans remaining (not in P0.3 scope)

| Artifact | Status |
| --- | --- |
| `horizon_validation.csv` | Exists; cross-regime validator checks presence only |
| `horizon_benchmark_summary.txt` | Manual chain; not in PAPER loop |
| `validation_horizon_summary.txt` | 30/90/180d rules; not wired |
| `intelligence/strategic_filter.py` | Zero importers |
| Live allocation enricher → `live_signals.csv` | Live path; forbidden for P0.3 |

---

## Safety confirmation

| Rule | Status |
| --- | --- |
| PAPER_ONLY | ✅ |
| NO_BROKER | ✅ |
| NO_LIVE_EXECUTION | ✅ |
| No new horizon engine | ✅ (read existing SSOT only) |
| Forbidden files untouched | ✅ (verified at commit) |

---

## Recommendations (future, not P0.3)

1. Refresh stale `historical_intelligence.csv` (~334h) via existing engine scripts.
2. Wire `tae_cross_validation_report.json` horizon slices into DPE philosophy weighting (read-only).
3. Add MOA summary section for horizon conflict counts from validation JSON.
