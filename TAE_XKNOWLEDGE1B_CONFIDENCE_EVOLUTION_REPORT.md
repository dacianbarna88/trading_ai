# TAE X.KNOWLEDGE-1B — Confidence Evolution / Score Decay After STOP Report

**Date:** 2026-07-02  
**Sprint:** X.KNOWLEDGE-1B  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Prior:** X.REPLAY-1 (NOT_READY) · X.COOLDOWN-1 (8/8 score persistence) · X.PROTECT-2 (26 obs)

---

## 1. Extension, not greenfield

Pre-build audit found extensive cognitive/evolution infrastructure (`learning_engine.py`, `promotion_gate.py`, hypothesis registry, meta evolution, confidence runtime, strategy evolution). **None were modified or rebuilt.**

X.KNOWLEDGE-1B fills the identified gap: **no module connected STOP→reentry→score persistence into confidence evolution** for the current intraday performance stack.

This sprint adds a **read-only extension VIEW** that:

- Reads COOLDOWN-1, X.REPLAY-1, PROTECT-2, and knowledge base outputs
- Emits confidence evolution entries and score-decay shadow candidates
- Produces `evidence_for_knowledge_base` for future **X.KNOWLEDGE-1C** ingest
- Does **not** write `tae_knowledge_base.json` or modify live scores

---

## 2. Sources reused

| Source | Role |
|--------|------|
| `tae_stop_reentry_cooldown_audit.json` | SSOT for score persistence, reentry sequences, cooldown simulation |
| `tae_decision_replay.json` | Primary/secondary failure causes from X.REPLAY-1 |
| `tae_profit_protection_validation.json` | PROTECT-2 gates, trailing hypothesis evidence |
| `tae_knowledge_base.json` | Baseline confidence levels (read-only) |
| `portfolio.csv` | Optional presence flag only (read-only) |

**Not reused / not called:** `promotion_gate.py`, `learning_engine.py`, `meta_evolution_engine.py`, `tae_confidence_runtime.py`.

---

## 3. Outputs generated

| File | Role |
|------|------|
| `tae_confidence_evolution.py` | Extension implementation |
| `tae_confidence_evolution_test.py` | 9 unit tests |
| `tae_confidence_evolution.json` | Structured confidence evolution VIEW |
| `tae_confidence_evolution.md` | Human-readable summary |

---

## 4. Live findings (2026-07-02)

### Dataset health

| Metric | Value |
|--------|-------|
| Stop→reentry cases | 8 |
| Score persistence cases | **8/8** |
| Second STOP cases | **2** |
| PROTECT-2 observations | 26 |
| Replay primary cause | MISSED_PROFIT_PROTECTION |
| Replay secondary cause | STOP_REENTRY_CHURN |
| Data quality | LIMITED (sample_warning) |

### Confidence evolution (selected)

| Hypothesis | Before → After | Trend | Status |
|------------|----------------|-------|--------|
| SCORE_PERSISTENCE_AFTER_STOP | HIGH → HIGH | IMPROVING | LEARNING |
| STOP_REENTRY_CHURN | LOW → MEDIUM | IMPROVING | WATCH |
| MISSED_PROFIT_PROTECTION | LOW → MEDIUM | IMPROVING | LEARNING |
| TRAILING_1_PROTECTION_HYPOTHESIS | LOW → MEDIUM | IMPROVING | WATCH |
| COOLDOWN_15M_HYPOTHESIS | LOW → MEDIUM | STABLE | DO_NOT_PROMOTE |

### Score decay shadow candidates

| Ticker | Original | Shadow | Window | Outcome |
|--------|----------|--------|--------|---------|
| MU | 100 | **80** | 30 min | REENTRY_SECOND_STOP (-75.71 USD) |
| MU | 100 | **80** | 30 min | REENTRY_OPEN (-24.75 USD est.) |

**Criteria:** STOP + reentry score ≥80 + immediate ≤5 min + (second STOP or negative outcome).  
**SIE.DE, PM, LLY excluded** — positive open/unrealized legs without second STOP.

### Promotion readiness

| Source | Status |
|--------|--------|
| PROTECT-2 | NOT_READY |
| COOLDOWN-1 | NOT_READY |
| **Composer final** | **NOT_READY** |

---

## 5. Limitations

1. **VIEW only** — live scores unchanged; `score_adjustment_shadow = -20` is advisory.
2. **Does not write knowledge base** — `evidence_for_knowledge_base` awaits X.KNOWLEDGE-1C.
3. **Sample size** — 8 reentry cases / 26 fade obs below advisory gates.
4. **Confidence delta capped** — LOW/MEDIUM/HIGH ordinal scale; not a calibrated probability.
5. **COOLDOWN_15M marked DO_NOT_PROMOTE** — net +23.98 USD but mixed winners (SIE.DE, MC.PA) vs MU damage.

---

## 6. Tests run

```text
python3 -m py_compile tae_confidence_evolution.py          # OK
python3 tae_confidence_evolution_test.py                    # 9/9 OK
python3 tae_confidence_evolution.py                         # OK
python3 -m py_compile live_bot.py tae_knowledge_base.py \
  tae_decision_replay_composer.py tae_stop_reentry_cooldown_audit.py \
  tae_profit_protection_validation.py                       # OK
```

Coverage: missing inputs, score persistence update, second STOP negative evidence, trailing hypothesis strengthening, NOT_READY gates, score decay shadow, no BUY/SELL, evidence_for_knowledge_base, markdown/json output.

---

## 7. Confirmations

| Constraint | Status |
|------------|--------|
| SHADOW_ONLY / PAPER_ONLY / NO_BROKER | ✅ |
| `live_bot.py` untouched | ✅ |
| BUY/SELL/Risk/Broker logic untouched | ✅ |
| `portfolio.csv` read-only | ✅ |
| `live_signals.csv` untouched | ✅ |
| `tae_knowledge_base.json` not written | ✅ |
| No git commit | ✅ |

---

## 8. Recommended next step

**X.KNOWLEDGE-1C — Knowledge Ingest Bridge**

Wire `evidence_for_knowledge_base` from `tae_confidence_evolution.json` into `tae_knowledge_base.py` materialization (read-only ingest path), so SCORE_DECAY_SHADOW and updated confidence trends appear in the knowledge VIEW without touching live scoring.

Continue observation until PROTECT-2 ≥30 obs and COOLDOWN-1 ≥10 cases before any shadow advisory promotion.

---

*Extension VIEW only. Does not execute trades or modify live_bot.*
