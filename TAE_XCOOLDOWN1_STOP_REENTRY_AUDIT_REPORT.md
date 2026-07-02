# TAE X.COOLDOWN-1 — Stop Re-entry Cooldown Shadow Audit Report

**Date:** 2026-07-02  
**Sprint:** X.COOLDOWN-1  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Prior:** X.PROTECT-2 — trailing validation NOT_READY (26 obs)

---

## 1. Problem observed

TAE exhibits **BUY → STOP → BUY** churn with high scores persisting after STOP:

| Ticker | Pattern | Timing |
|--------|---------|--------|
| MU | STOP → BUY → second STOP → BUY | ~1 min each |
| PM | STOP → BUY | ~1.3 min |
| LLY | STOP → BUY | ~1.3 min |
| MC.PA | STOP → BUY | ~103 min (same session) |
| SIE.DE | STOP → BUY | ~1.3 min |

Hypothesis: immediate re-entry after STOP compounds losses without new confirmation.

---

## 2. Methodology

1. Parse `portfolio.csv` chronologically (read-only)
2. Detect **STOP LOSS** SELL events (`Reason` contains `STOP LOSS`)
3. Match first subsequent **BUY** on same ticker
4. Classify timing: IMMEDIATE (≤5m), FAST (≤30m), SAME_SESSION, NEXT_SESSION
5. Compute reentry leg PnL:
   - **ACTUAL** — from subsequent SELL row(s) in portfolio
   - **ESTIMATED** — open leg from latest ticker row snapshot
6. Simulate cooldown policies (counterfactual block + net PnL effect)
7. Audit score persistence (reentry score ≥80 + STRONG BUY after STOP)
8. Apply gates G1–G5 for advisory readiness

Optional inputs: `live_signals.csv`, `tae_accounting_snapshot.json` (context only; not required).

---

## 3. Live results (2026-07-02)

### Summary

| Metric | Value |
|--------|-------|
| Portfolio rows | 82 |
| Total STOP events | **15** |
| Reentries after STOP | **8** |
| Immediate (≤5 min) | **5** |
| Fast (≤30 min) | 5 |
| Same session | 6 |
| Second STOP after reentry | **2** |
| Total reentry leg PnL | **+114.94 USD** (mixed; open legs ESTIMATED) |

### Notable immediate reentries (2026-07-01)

| Ticker | Δt | Score | Outcome | Leg PnL |
|--------|-----|-------|---------|---------|
| MU | 1.3m | 100 | **REENTRY_SECOND_STOP** | **-75.71** (ACTUAL) |
| MU | 1.3m | 100 | OPEN | -24.75 (ESTIMATED) |
| PM | 1.3m | 80 | OPEN | +2.54 (ESTIMATED) |
| LLY | 1.3m | 100 | OPEN | +27.46 (ESTIMATED) |
| SIE.DE | 1.3m | 80 | REENTRY_WIN | +46.48 (ACTUAL) |

**Key finding:** MU immediate re-entry produced a **confirmed second STOP (-75.71 USD)** — clearest damage case. PM/LLY immediate re-entries currently flat/small open PnL. Aggregate reentry PnL is positive due to MC.PA (+87 ESTIMATED) and SIE.DE (+46) — cooldown is **not universally beneficial** on this small sample.

---

## 4. Cooldown simulations

| Policy | Blocked | Avoided loss | Missed gain | **Net effect** |
|--------|---------|--------------|-------------|----------------|
| **cooldown_15m** | 5 | 100.46 | 76.48 | **+23.98** |
| cooldown_30m | 5 | 100.46 | 76.48 | +23.98 |
| cooldown_60m | 5 | 100.46 | 76.48 | +23.98 |
| cooldown_until_next_session | 6 | 100.46 | 163.75 | -63.29 |
| cooldown_until_new_confirmation | 8 | 100.46 | 215.40 | -114.94 |

**Best cooldown (net):** `cooldown_15m` / `30m` / `60m` (tie on this dataset — all immediate reentries ≤5m)

Interpretation: blocking immediate re-entries would have **avoided ~100 USD losses** (mostly MU second leg) but **missed ~76 USD gains** (SIE.DE, LLY, PM open) → net **+24 USD** on counterfactual — modest, **ESTIMATED** for open legs.

---

## 5. Score persistence after STOP

| Metric | Value |
|--------|-------|
| Cases (score ≥80 + STRONG BUY) | **8 / 8** (100%) |
| Average leg PnL | +14.37 USD |
| Loss rate | **25%** |
| Second STOP rate | **25%** |

All recent reentries retained high scores — score engine does not decay confidence after STOP. However **loss rate 25% < 50%** gate threshold because several open/profitable reentries (MC.PA, LLY, SIE.DE) offset MU damage on this sample.

---

## 6. Gates G1–G5

| Gate | Criterion | Result |
|------|-----------|--------|
| G1 | ≥10 stop-reentry cases | **FAIL** (8) |
| G2 | cooldown net_effect > 0 | **PASS** (+23.98) |
| G3 | second_stop rate ↓ ≥30% | **FAIL** (-33% on 15m sim*) |
| G4 | missed ≤ 50% of avoided | **FAIL** (76.48 > 50.23) |
| G5 | persistence loss rate > 50% | **FAIL** (25%) |

\*Small-sample artifact: blocking 1 of 2 second stops changes rate non-intuitively with only 8 cases.

**Advisory readiness:** **NOT_READY**  
**Verdict:** **INSUFFICIENT_SAMPLE**

---

## 7. Tests

```bash
python3 -m py_compile tae_stop_reentry_cooldown_audit.py   # OK
python3 tae_stop_reentry_cooldown_audit_test.py            # 15/15 OK
python3 tae_stop_reentry_cooldown_audit.py                 # OK
python3 -m py_compile live_bot.py tae_profit_protection_validation.py \
  tae_profit_protection_shadow.py tae_intraday_fade_history.py  # OK
```

Coverage: STOP→BUY detection, timing classes, second STOP, win/loss, cooldown block/net effect, score persistence, NOT_READY small sample, no live recommendations, missing input, JSON/MD output.

---

## 8. Confirmations

| Check | Status |
|-------|--------|
| SHADOW_ONLY | **YES** |
| PAPER_ONLY | **YES** |
| NO_BROKER | **YES** |
| No live BUY/SELL | **YES** |
| `live_bot.py` untouched | **YES** |
| `portfolio.csv` untouched | **YES** |
| `live_signals.csv` untouched | **YES** |
| Git commit | **NO** |

---

## 9. Verdict — does cooldown merit further investigation?

**YES — WATCH level, not advisory.**

Evidence supporting cooldown research:

- **5 immediate reentries** in recent session; MU → second STOP is concrete -75.71 USD damage
- **100% score persistence** after STOP (STRONG BUY 80–100)
- **15m cooldown net +24 USD** counterfactual on current sample

Evidence against premature live cooldown:

- Only **8** reentry cases (G1 fail)
- Aggregate reentry PnL **positive** (+115 USD) — winners exist (MC.PA, SIE.DE)
- G4 fail — missed winners are material vs avoided losses
- Open leg PnL uses **ESTIMATED** methodology

**Do NOT promote to live.** Recommend **TEST_15M_COOLDOWN_SHADOW** observation only.

---

## 10. Recommended next step

**Proceed to X.REPLAY-1** — integrate:

- X.PROTECT-2 exit counterfactuals (trailing +579 USD)
- X.COOLDOWN-1 re-entry counterfactuals (MU second STOP -75 USD)
- Per-decision failure mode: EXIT vs REENTRY vs ENTRY

Continue accumulating stop-reentry cases until G1 ≥10 before any shadow advisory promotion.

---

*TAE X.COOLDOWN-1 — stop re-entry cooldown shadow audit. Research only; no execution.*
