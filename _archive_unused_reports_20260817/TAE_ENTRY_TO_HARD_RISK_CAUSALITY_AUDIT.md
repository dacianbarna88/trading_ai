# TAE Entry → Hard Risk Causality Audit

**Sprint:** `ENTRY_TO_HARD_RISK_CAUSALITY_AUDIT`  
**Mode:** READ_ONLY | PAPER_ONLY | NO_CODE_CHANGE  
**Generated:** 2026-08-03  
**Prior finding:** Hard Risk crystallization is the *loss mechanism*. This audit asks why those positions were **bought**.

## FINAL_VERDICT

**`TAE_ROOT_CAUSE_OF_HARD_RISK_IDENTIFIED`**

### Root cause (one sentence)

**STRONG BUY (score≈100) authorization opens risk even when Decision Brain / longitudinal memory says SKIP (and often PPG PROTECT / 7D-NEGATIVE), while learning tags are present on the BUY reason but non-blocking — Hard Risk later crystallizes the drawdown that entry already made possible.**

Hard Risk is the **closer**. Entry override of protective SKIP/PROTECT is the **cause**.

---

## 1. Cohort definition

| Cohort | Definition | V1 n | V2 n |
| --- | --- | ---: | ---: |
| HARD_RISK_STOP | Order reason contains HARD_STOP / HARD RISK −3% | 10 sells | 0 closes* |
| HARD_RISK_CRITICAL | HARD_CRITICAL / FORCE −5% | 2 sells | 3 closes |
| TRAILING_LOSS | PROFIT_TRAILING exit with realized ≤ 0 | 4 sells | 0 |
| IMMEDIATE (&lt;24h) | Hold &lt; 24h into HR/trailing-loss | 4 | SAP same-day CRITICAL |
| OPEN_DRAWDOWN | Still open, uPnL &lt; −$5 (vulnerability not yet crystallized) | — | 5 |

\*V2 price −3% is informational during accumulation; crystallization observed as CRITICAL closes.

**V1 provenance:** 9/16 loss cases join to an executed BUY journal row; **7 are orphans** (sell without matching BUY in `paper_trades` / orders — pre-journal or incomplete entry SSOT). Orphans are reported for exit class but excluded from entry-pattern percentages unless noted.

---

## 2. Timeline template (reconstructed)

```
Market / signal snapshot (STRONG BUY, score≈100)
        ↓
Decision Brain / longitudinal memory (often SKIP_PAPER, sometimes PROTECT_SHADOW, sometimes 7D NEGATIVE)
        ↓
PDE / paper decision (may score SKIP highest *now*; historical BUY used signal path)
        ↓
BUY authorization  ← BREAK POINT (SKIP→BUY or new_decision despite mem SKIP)
        ↓
Execution (paper fill)
        ↓
Price evolution / first drawdown
        ↓
(optional) Trailing arm / protect soft path
        ↓
Hard Risk threshold (−3% / −5%)  ← CRYSTALLIZATION
        ↓
Settlement (realized loss)
        ↓
Learning (tags logged; lifecycle stays TESTING; influence_delta≈0)
```

**Break point:** protective Decision Brain / PPG output is **not a binding gate** on BUY.

---

## 3. V1 attributed cases (journal BUY → HR / trailing loss)

| ticker | exit | realized | hold_h | imm | score | signal | buy path | mem_action | mem_7d | PPG | neg signals ignored |
| --- | --- | ---: | ---: | --- | ---: | --- | --- | --- | --- | --- | --- |
| MU | HR_CRIT | −163.10 | 0.31 | Y | —* | STRONG BUY | new_decision | SKIP | POS | PROTECT_SHADOW | SKIP, PPG |
| AMAT | HR_STOP | −122.41 | 0.31 | Y | 100 | STRONG BUY | new_decision | SKIP | **NEG** | PROTECT_SHADOW | SKIP, 7D_NEG, PPG |
| AMAT | HR_STOP | −22.99 | 22.6 | Y | 100 | STRONG BUY | new_decision | SKIP | **NEG** | PROTECT_SHADOW | SKIP, 7D_NEG, PPG |
| HD | TRAIL 0 | 0.00 | 7.35 | Y | 100 | STRONG BUY | new_decision | SKIP | NEU | — | SKIP, GROWTH_0 |
| GE | HR_STOP | −21.84 | 470 | N | 100 | STRONG BUY | **SKIP→BUY** | SKIP | NEU | — | SKIP, GROWTH_0 |
| GE | HR_STOP | −12.00 | 161 | N | 100 | STRONG BUY | **SKIP→BUY** | SKIP | NEU | — | SKIP, GROWTH_0 |
| NVDA | HR_STOP | −18.50 | 74 | N | 100 | STRONG BUY | **SKIP→BUY** | SKIP | NEU | — | SKIP, GROWTH_0 |
| LLY | HR_STOP | −14.46 | 479 | N | 100 | STRONG BUY | SELL→BUY | SKIP | POS | TRAIL_SHADOW | SKIP, PPG |
| SIE.DE | HR_STOP | −13.62 | 65 | N | 100 | STRONG BUY | **SKIP→BUY** | SKIP | **NEG** | — | SKIP, 7D_NEG |

\*MU reason text has STRONG BUY without numeric `score=`; same HIGH_RISK/CAPITAL_PRESERVATION_SHADOW policy family.

**Orphan exits (no BUY join):** SIE.DE −142.49, MC.PA −98.38, LLY −94.15, MRK trail −93.57, PM trail −87.18, AAPL trail −39.69, QQQ −10.43 → **ENTRY_PROVENANCE_GAP** (cannot audit buy causality; exit still HR/trailing).

### V1 pattern rates (attributed n=9)

| Pattern | Count | Rate | USD of attributed losses |
| --- | ---: | ---: | ---: |
| STRONG BUY at entry | 9/9 | **100%** | −388.92 |
| score = 100 (when parsed) | 8/9 | **89%** | — |
| Longitudinal mem_action = SKIP_PAPER | 9/9 | **100%** | −388.92 |
| Learning tags on BUY reason | 9/9 | **100%** | — |
| Explicit `SKIP_PAPER→BUY_PAPER` | 4/9 | 44% | −65.97 |
| 7D NEGATIVE at entry | 3/9 | 33% | −159.01 |
| PPG PROTECT/TRAIL shadow | 4/9 | 44% | −322.95 |
| Immediate &lt;24h | 4/9 | 44% | −308.49 |
| policy HIGH_RISK/…SHADOW | 5/9 | 56% | — |

**First vulnerability events (attributed):**

1. **BUY despite Decision Brain SKIP** (universal in attributed set)  
2. **Entry into active 7D downtrend** (AMAT, SIE)  
3. **Entry while PPG PROTECT_SHADOW** (MU, AMAT)  
4. Then **immediate adverse move** (MU/AMAT hours) or multi-day path to −3%/−5%

---

## 4. V2 OPEN → CRITICAL / open drawdown

| ticker | score | mem before OPEN | outcome | PnL |
| --- | ---: | --- | --- | ---: |
| MSFT | 100 | SKIP | CLOSE_HARD_RISK_CRITICAL | −51.57 |
| NVDA | 100 | PROTECT_PAPER | CLOSE_HARD_RISK_CRITICAL | −25.99 |
| SAP.DE | 100 | SKIP | CLOSE_HARD_RISK_CRITICAL | −29.59 |
| ABBV | 100 | SKIP | open DD | −26.82 |
| MRK | 100 | HOLD | open DD | −16.86 |
| AIR.PA | 100 | SKIP | open DD | −6.06 |
| PG | 80 | HOLD + **7D NEG** | open DD | −13.56 |
| LLY | 80 | PROTECT | open DD | −30.87 |

All OPENs: reason `OPEN_VALID_CANDIDATE`, tranche_count=1.

### Histogram (calculated): entry score → outcome (V2 all 15 OPENs)

| Score bucket | n | HR CRITICAL rate | Avg PnL (R or u) |
| --- | ---: | ---: | ---: |
| **100** | 8 | **37.5%** (3/8) | **−14.77** |
| **80–99** | 7 | **0%** (0/7) | **+0.45** |

This is the sharpest **entry-quality** signal in the sample: score=100 cohort concentrates Hard Risk; score=80 cohort does not (in this window).

---

## 5. Causality answers (per loss class)

### For each Hard Risk / trailing-loss (attributed)

1. **First event making position vulnerable?** Opening the BUY while protective SKIP (and often PROTECT / 7D_NEG) was already on the record.  
2. **Negative signals already present?** **Yes** for the majority of attributed cases (SKIP 100%; PPG and/or 7D_NEG in 33–44%).  
3. **Ignored?** **Yes.**  
4. **By whom?**  
   - **Decision Brain SKIP** — produced but overridden  
   - **PPG / profit-protection posture** — present, non-blocking on entry  
   - **Horizon 7D NEGATIVE** — present on AMAT/SIE, non-blocking  
   - **Learning tags** — printed on BUY reason, **non-blocking** (TESTING, influence_delta=0)  
   - **Not primarily Trailing/Sizing** at the *start* (sizing amplifies USD; trailing is later exit class)  
5. **Learning had the info?** Tags `MISSED_PROFIT_PROTECTION`, `STOP_REENTRY_CHURN`, `SCORE_DECAY_SHADOW` appear **on the BUY reason itself**.  
6. **Why no BUY influence?** Lifecycle state **TESTING**, `ACTIVE=[]`, `recommended_influence_delta=0` on those rules — chain stops at **Decision Delta**.  
7. **Why no learn-after-first?** After MU/AMAT immediate HR (2026-07-08), later GE/NVDA/SIE still bought via SKIP→BUY / STRONG BUY — **no binding update** from prior similar STOP outcomes.

---

## 6. Stop cluster (common patterns)

| Cluster feature | Evidence |
| --- | --- |
| Signal class | STRONG BUY dominates attributed V1 entries |
| Score | ≈100 on V1 attributed; V2 HR closes all score=100 |
| Decision memory | SKIP_PAPER before entry (V1 9/9 attributed) |
| Sector tilt | SEMI (MU, AMAT, NVDA) + HEALTH (LLY) + INDUSTRIAL (GE, SIE) heavy in HR USD |
| Regime label | market_regime often **BULL** in memory — not a bear-filter failure; short-term horizon conflict is the miss |
| Volatility | mostly UNKNOWN in memory — **not discriminative** here |
| Holding | bimodal: immediate hours (MU/AMAT) vs multi-day grind to −3% |
| Learning | tags present, never ACTIVE |
| Policy paradox | `HIGH_RISK/CAPITAL_PRESERVATION_SHADOW` co-occurs with BUY (preservation is shadow, not a hard veto) |

---

## 7. False positives / missed wins

### Most expensive wrong BUYs (attributed + largest orphans)

| Rank | ticker | realized | why “wrong” at entry |
| ---: | --- | ---: | --- |
| 1 | MU | −163.10 | SKIP+PROTECT ignored; CRIT in 0.3h |
| 2 | SIE.DE | −142.49 | orphan entry SSOT; HR STOP |
| 3 | AMAT | −122.41 | SKIP+7D_NEG+PROTECT ignored |
| 4 | MC.PA | −98.38 | orphan; CRITICAL |
| 5 | LLY | −94.15 | orphan then later rebuy also HR |

### Profitable BUYs that SKIP binding would have missed

If every `SKIP_PAPER→BUY_PAPER` had been blocked:

| ticker | win realized that would be missed |
| --- | ---: |
| AIR.PA | +22.80 |
| ULVR.L | +16.33 |
| ABBV | +0.84 |
| **Sum missed wins** | **+39.97** |

Attributed HR losses avoidable by binding SKIP on that cohort: **+$388.92**.  
**Net counterfactual (avoid attributed losses − miss those wins) ≈ +$348.95** (order of magnitude; orphans not included).

---

## 8. Counterfactuals (no strategy change — arithmetic only)

For each attributed V1 loss case:

| CF | Rule | Result |
| --- | --- | --- |
| SKIP | Never enter | realized → **0**; avoid `abs(loss)` |
| HOLD / WAIT as non-entry | Same as SKIP if no fill | same |
| HALF SIZE | `realized/2` | e.g. MU −81.55 instead of −163.10 |
| FIRST TRANCHE ONLY | V1 already full-size paper buys — N/A as V2 concept | — |
| WAIT 1–2 DAYS | **Not priced** — no local OHLC SSOT for entry dates in this audit; **TRUE_DATA_GAP** for path CF |

**V2:** already FIRST TRANCHE ONLY ($500). HALF SIZE → ≈ half CRITICAL USD (−53.58 vs −107.16). SKIP on score=100 OPENs would remove all 3 CRITICAL closes (−107.16) and also remove PM trailing win (+23.44) if PM were included in a blanket score=100 ban — selective gate needed.

**Immediate cluster CF:** SKIP on MU+AMAT alone avoids **−$308.49** of immediate losses.

---

## 9. Learning chain (where it stops)

```
Learning observes tags / HR outcomes
        ↓
Decision Delta  ← STOPS HERE (influence_delta=0, state=TESTING, ACTIVE=[])
        ↓
Execution        (BUY still authorized on STRONG BUY)
        ↓
Outcome          (HR crystallization)
        ↓
Next similar trade (GE/NVDA/SIE after MU/AMAT) — SAME PATH
```

**Verdict:** Learning **records** but does **not** change entry. Not a missing module — an **unpromoted / non-binding** influence path.

---

## 10. Final answers

### 1. Root cause of Hard Risk?

**Entry authorization that treats STRONG BUY (score≈100) as sufficient to open risk while Decision Brain SKIP / PPG PROTECT / short-term negative signals are non-binding.** Hard Risk is the downstream crystallization of that entry.

### 2. Entry / Timing / Forecast / Regime / Sizing / Learning / combo?

**Combination, dominated by Entry + Timing wiring:**

| Factor | Role |
| --- | --- |
| **Entry** | Primary — BUY opened against SKIP/PROTECT |
| **Timing** | Secondary — immediate cluster; 7D_NEG ignored |
| **Forecast / Regime** | Labels often BULL; not the binding miss; short-term horizon is |
| **Sizing** | Amplifier of USD, not why entry occurred |
| **Learning** | Present but inert at entry |
| **Hard Risk** | Mechanism of loss, not root of purchase |

### 3. Existing component that could prevent?

**Decision Brain / longitudinal SKIP** and **PPG PROTECT_SHADOW** — if binding on new BUY.  
Secondary: learning promotion of STOP_REENTRY / MISSED_PROFIT rules to nonzero influence.

### 4. Connected?

| Component | Status |
| --- | --- |
| Decision Brain SKIP | **EXISTS_NOT_WIRED as hard gate** (wired as advisory; overridden by BUY) |
| PPG PROTECT_SHADOW | **EXISTS_NOT_WIRED as entry veto** |
| Learning tags on BUY | **WIRED as annotation only** (not economic control) |
| Hard Risk guardian | **ACTIVE + WIRED** (exit) |
| V2 OPEN_VALID_CANDIDATE | **ACTIVE + WIRED** (entry) |
| Score=100 vs 80 separation | **TRUE GAP in entry filter** (evidence exists; no gate uses it) |

### 5. First real economic sprint (do not implement here)

**Binding protective-SKIP / PPG-PROTECT entry gate — measurement then controlled PAPER experiment**  
Compare actual book vs counterfactual where BUY is blocked when `mem_action=SKIP_PAPER` or `ppg_posture=PROTECT_SHADOW` (and optionally when score≥100 **and** 7D_NEGATIVE).  
Prior arithmetic: ~**+$349** net on attributed SKIP-override subset alone; V2 score bucket already shows 37.5% vs 0% HR rate.

Not V3. Not new models. Not changing Hard Risk thresholds in this sprint.

---

## Deliverables

- `tae_entry_to_hard_risk_causality_audit.json`  
- Canvas: `entry-to-hard-risk-causality.canvas.tsx`

**No BUY / SELL / Hard Risk / V1 / V2 code was modified.**

```
FINAL_VERDICT=TAE_ROOT_CAUSE_OF_HARD_RISK_IDENTIFIED
```

STOP.
