# TAE X.REPLAY-1 — Unified Decision Replay Composer Report

**Date:** 2026-07-02  
**Sprint:** X.REPLAY-1  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Prior:** X.PROTECT-2 (NOT_READY, 26 obs) · X.COOLDOWN-1 (NOT_READY, 8 reentry cases)

---

## 1. Why this is a composer, not a duplicate

Pre-build audit confirmed substantial prior art:

| Existing artifact | Role | X.REPLAY-1 relationship |
|-------------------|------|-------------------------|
| `decision_replay_engine.py` (V31.1) | Legacy per-decision replay | **Not replaced** — predates current performance stack |
| `research_core/profit_attribution/` | Profit attribution engine | **Reused** via optional `tae_profit_attribution.json` |
| `tae_profit_protection_validation.py` (PROTECT-2) | SSOT for shadow exit validation | **Read-only input** |
| `tae_stop_reentry_cooldown_audit.py` (COOLDOWN-1) | SSOT for STOP→BUY reentry audit | **Read-only input** |
| `tae_accounting_snapshot.py` | Canonical PnL SSOT | **Read-only input** |
| `tae_knowledge_base.py` | Materialized knowledge VIEW | **Read-only input** |

X.REPLAY-1 adds a **consolidation layer** that:

- Normalizes upstream JSON into one replay VIEW
- Classifies failure modes across domains (ENTRY / EXIT / REENTRY / PROTECTION / LEGACY / DATA)
- Ranks top costly decisions with evidence pointers
- Compares counterfactuals without rebuilding simulation logic
- Merges promotion readiness from existing gates — **no new promotion gate**

It does **not** modify BUY/SELL/Risk/Broker logic, `live_bot.py`, `portfolio.csv`, or `live_signals.csv`.

---

## 2. Sources reused

### Required (when available)

| Source | SSOT for |
|--------|----------|
| `portfolio.csv` | Legacy CLOSED_FREEZE drag scan (read-only) |
| `tae_accounting_snapshot.json` | Realized / unrealized / total PnL |
| `tae_profit_protection_validation.json` | Shadow trailing validation (PROTECT-2) |
| `tae_stop_reentry_cooldown_audit.json` | STOP→BUY cooldown audit (COOLDOWN-1) |
| `tae_knowledge_base.json` | Confirmed fade / protection / reentry patterns |

### Optional

| Source | Use |
|--------|-----|
| `tae_profit_attribution.json` | Context only (not rebuilt) |
| `tae_performance_pipeline_report.json` | Pipeline health flag |
| `decision_registry.csv` | Decision registry presence |
| `decision_replay_summary.txt` | Legacy replay engine output if present |

Missing optional files are marked explicitly; values are never invented. Uncertain combined effects are labeled **ESTIMATED**.

---

## 3. Outputs generated

| File | Role |
|------|------|
| `tae_decision_replay_composer.py` | Composer implementation |
| `tae_decision_replay_composer_test.py` | 10 unit tests |
| `tae_decision_replay.json` | Structured unified replay VIEW |
| `tae_decision_replay.md` | Human-readable summary |

---

## 4. Live findings (2026-07-02)

### PnL summary (accounting SSOT)

| Metric | Value |
|--------|-------|
| Total trading PnL | **-22.49 USD** |
| Realized PnL | +36.65 USD |
| Unrealized PnL | -59.15 USD |
| Open positions | 12 |

### Failure mode attribution

| Mode | Severity | Detail |
|------|----------|--------|
| **MISSED_PROFIT_PROTECTION** | HIGH | Shadow trailing Δ vs HOLD **+616.18 USD** (PROTECT-2) |
| **STOP_REENTRY_CHURN** | HIGH | 5 immediate reentries after STOP (COOLDOWN-1) |
| **SCORE_PERSISTENCE_AFTER_STOP** | MEDIUM | 8/8 reentries with score≥80 + STRONG BUY |
| **LEGACY_CLOSED_FREEZE_DRAG** | MEDIUM | CLOSED_FREEZE cumulative drag **-786.26 USD** |

### Counterfactual comparison

| Metric | Value |
|--------|-------|
| HOLD baseline (shadow book) | -37.13 USD |
| Best protection (`shadow_trailing_1`) | 579.05 USD |
| Protection Δ vs HOLD | **+616.18 USD** |
| Best cooldown (`cooldown_15m`) net | **+23.98 USD** |
| Combined (ESTIMATED) | **640.16 USD** ⚠️ double-count warning |

Combined effect is **ESTIMATED** — protection and cooldown may overlap on MU, PM, LLY.

### Top costly decisions

| Rank | Ticker | Event | Est. Δ | Failure mode |
|------|--------|-------|--------|--------------|
| 1 | MU | INTRADAY_FADE (+5.22% then fade) | 269.72 USD | MISSED_PROFIT_PROTECTION |
| 2 | PM | INTRADAY_FADE | 184.20 USD | MISSED_PROFIT_PROTECTION |
| 3 | LLY | INTRADAY_FADE | 175.14 USD | MISSED_PROFIT_PROTECTION |
| 4 | AZN.L | INTRADAY_FADE | 123.48 USD | MISSED_PROFIT_PROTECTION |
| 5 | MRK | INTRADAY_FADE | 118.04 USD | MISSED_PROFIT_PROTECTION |
| 6 | SIE.DE | INTRADAY_FADE | 112.60 USD | MISSED_PROFIT_PROTECTION |
| 7 | MU | STOP→BUY→second STOP | 75.71 USD | STOP_REENTRY_CHURN |

### Promotion readiness

| Source | Status | Gates passed |
|--------|--------|--------------|
| PROTECT-2 | NOT_READY | False (G1: 26/30 obs, G3: 54% win rate) |
| COOLDOWN-1 | NOT_READY | False (G1: 8/10 cases) |
| **Composer final** | **NOT_READY** | — |

### Final verdict

- **Primary cause:** MISSED_PROFIT_PROTECTION (intraday gains evaporate without shadow trailing)
- **Secondary cause:** STOP_REENTRY_CHURN (immediate high-score reentry after STOP)
- **Best shadow hypothesis:** `shadow_trailing_1`
- **Do NOT promote:** shadow advisory, live trailing, or cooldown enforcement until gates pass

---

## 5. Limitations

1. **Composer VIEW only** — upstream SSOT files remain authoritative; stale inputs produce stale replay.
2. **Combined counterfactual is ESTIMATED** — protection and cooldown effects are not event-disjoint; additive total is indicative, not proof.
3. **Legacy replay engine not integrated** — `decision_replay_engine.py` output is optional context only; current stack uses PROTECT-2 + COOLDOWN-1.
4. **Attribution not rebuilt** — `research_core/profit_attribution/` consumed only if JSON exists.
5. **Sample size** — PROTECT-2 (26 obs) and COOLDOWN-1 (8 reentry cases) both below advisory gates.
6. **Knowledge base is a VIEW** — entries inform context but are not validation SSOT.

---

## 6. Tests run

```text
python3 -m py_compile tae_decision_replay_composer.py          # OK
python3 tae_decision_replay_composer_test.py                    # 10/10 OK
python3 tae_decision_replay_composer.py                         # OK — outputs written
python3 -m py_compile live_bot.py tae_profit_protection_validation.py \
  tae_stop_reentry_cooldown_audit.py tae_knowledge_base.py \
  tae_accounting_snapshot.py                                    # OK
```

Test coverage:

- Missing optional inputs handled gracefully
- PROTECT-2 / COOLDOWN-1 / accounting normalization
- Failure mode classification (including source-key fix for PROTECT-2 presence)
- Combined estimate with double-count warning
- Top costly decision ranking
- NOT_READY when upstream gates fail
- No BUY/SELL live recommendations in output
- Markdown + JSON output schema

---

## 7. Confirmations

| Constraint | Status |
|------------|--------|
| SHADOW_ONLY / PAPER_ONLY / NO_BROKER | ✅ Confirmed |
| `live_bot.py` untouched | ✅ Confirmed |
| `portfolio.csv` read-only | ✅ Confirmed |
| `live_signals.csv` untouched | ✅ Confirmed |
| No new promotion gate created | ✅ Confirmed |
| No git commit | ✅ Confirmed (per sprint instruction) |

---

## 8. Recommended next step

**Continue observation** until PROTECT-2 reaches ≥30 fade observations (G1), then proceed to:

**X.KNOWLEDGE-1B — Confidence Evolution** (score decay after STOP)

Rationale: COOLDOWN-1 shows 8/8 score persistence after STOP; combined with MISSED_PROFIT_PROTECTION as primary cause, the next highest-value shadow work is modeling score decay rather than finer-grained replay (X.REPLAY-2) until sample gates pass.

Alternative if composer granularity is needed first: **X.REPLAY-2** (per-event overlap analysis to de-duplicate combined counterfactual).

---

*Composer VIEW only. Does not execute trades or modify live_bot.*
