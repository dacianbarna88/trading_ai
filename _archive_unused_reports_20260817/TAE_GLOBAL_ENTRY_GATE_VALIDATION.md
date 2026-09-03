# TAE Global Entry Gate Validation

**Sprint:** `GLOBAL_ENTRY_GATE_VALIDATION`  
**Mode:** READ_ONLY | PAPER_ONLY | NO_CODE_CHANGE  
**Generated:** 2026-08-03  
**Universe:** **All** historical V1 BUY fills (n=20) + **all** V2 OPEN fills (n=15) — not loss-only.

## FINAL_VERDICT

**`GLOBAL_ENTRY_GATE_PROVEN`**

Proven as:

1. **Statistical predictor:** Decision Brain `SKIP` elevates loss rate and Hard Risk rate vs non-SKIP (V1 lift **2.67×** on loss rate; V2 SKIP loss rate **80%**).  
2. **Economic gate candidate (global):** Binding SKIP on **V1+V2 combined** improves net PnL by **+$107.59**, raises ROI **0.20% → 1.62%**, cuts HR **37.1% → 13.3%**.  
3. **V2-specific:** Binding SKIP alone saves **+$111.02** net.

**Not proven / rejected as hard gates:**

- **PPG PROTECT alone** — destroys winners (combined net **−$121.53**). Use as soft bias only.  
- **Unconditional V1-only SKIP hard gate** — net ≈ **−$3.43** on current MTM (open winners with prior SKIP, e.g. SAP.DE / SIE.DE). Still improves expectancy/ROI of *kept* book, but absolute PnL is not clearly better on V1 alone.

---

## 1. Method

| Step | Detail |
| --- | --- |
| V1 entries | Every `EXECUTED` BUY in `paper_orders` / `paper_trades` (20 lots) |
| V2 entries | Every `OPEN` in V2 decisions + cycle_state (15) |
| Decision Brain | Longitudinal memory action **≤ entry ts**: BUY / SKIP / HOLD |
| PPG | `ppg_posture` / `profit_protection_state`: PROTECT (incl. TRAIL shadow) vs ALLOW |
| Forecast | `short_term_trend_7d`: 7D_NEGATIVE / POSITIVE / NEUTRAL |
| Outcome PnL | Closed: FIFO-allocated realized; Open: mark-to-market unrealized (V1 MTM / V2 portfolio) |
| Exit class | From sell-order reason when closed; else OPEN |

**Caveats:** V1 n=20, V2 n=15 — small. Open MTM dominates V1 total (+150). Orphan historical sells without BUY lots are outside this BUY universe by design.

---

## 2. Universe scoreboard

| Strategy | Buys | Wins | Losses | Total PnL | ROI on size | Expectancy | HR% | Loss% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 20 | 10 | 9 | **+150.13** | +1.53% | +7.51 | 50.0% | 45.0% |
| V2 | 15 | 6 | 9 | **−115.05** | −1.53% | −7.67 | 20.0% | 60.0% |
| Combined | 35 | 16 | 18 | **+35.08** | +0.20% | +1.00 | 37.1% | 51.4% |

---

## 3. Class metrics — V1

### Decision Brain

| Class | n | W/L | Total PnL | ROI% | Exp | PF | HR% | Loss% | Avg hold (h) |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **SKIP** | 15 | 6/8 | +3.43 | +0.06 | +0.23 | 1.04 | **60.0** | **53.3** | — |
| **BUY** | 4 | 3/1 | +118.52 | +3.47 | +29.63 | 7.73 | 25.0 | 25.0 | — |
| **HOLD** | 1 | 1/0 | +28.18 | +7.48 | +28.18 | ∞ | 0.0 | 0.0 | — |

**Loss-rate lift SKIP vs other:** 53.3% / 20.0% = **2.67×**.  
**HR-rate:** SKIP 60% vs BUY 25%.

### PPG

| Class | n | W/L | Total PnL | ROI% | Exp | PF | HR% | Loss% |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PROTECT | 10 | 5/5 | **+129.75** | +2.49 | +12.98 | 3.05 | **70.0** | 50.0 |
| ALLOW | 10 | 5/4 | +20.38 | +0.44 | +2.04 | 1.39 | 30.0 | 40.0 |

PPG PROTECT predicts **higher HR%** but also holds the largest **open winners** (SAP/SIE) → bad as sole hard eliminate rule.

### Forecast 7D

| Class | n | W/L | Total PnL | ROI% | Exp | PF | HR% | Loss% |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **7D_NEGATIVE** | 4 | 1/3 | −7.23 | −0.58 | −1.81 | 0.83 | **100** | **75.0** |
| 7D_POSITIVE | 3 | 1/2 | +0.86 | +0.07 | +0.29 | 1.04 | 100 | 66.7 |
| 7D_NEUTRAL | 13 | 8/4 | +156.50 | +2.15 | +12.04 | 3.99 | 23.1 | 30.8 |

7D_NEG: strongest **HR coincidence** (100%) but **n=4** and one win (MRK) — predictor of HR path, weak standalone economics.

---

## 4. Class metrics — V2

### Score buckets (reconfirmed on full OPEN universe)

| Score | n | W/L | Total PnL | ROI% | Exp | PF | HR% | Loss% |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **100** | 8 | 2/6 | **−118.19** | −2.95 | −14.77 | 0.25 | **37.5** | **75.0** |
| **80–99** | 7 | 4/3 | **+3.14** | +0.09 | +0.45 | 1.07 | **0.0** | 42.9 |

### Decision Brain / PPG / Forecast (V2)

| Class | n | Loss% | HR% | Total PnL |
| --- | ---: | ---: | ---: | ---: |
| DB=SKIP | 5 | **80.0** | 40.0 | **−111.02** |
| DB=HOLD | 10 | 50.0 | 10.0 | −4.03 |
| PPG=PROTECT | 7 | 42.9 | 14.3 | −8.22 |
| PPG=ALLOW | 8 | **75.0** | 25.0 | −106.83 |
| FC=7D_NEG | 3 | 33.3 | 0.0 | **+27.59** (includes ULVR trail win) |
| FC=7D_NEUTRAL | 8 | 75.0 | 37.5 | −133.61 |

On V2, **SKIP** and **score=100** dominate economic damage; **7D_NEG is not the V2 villain** in this sample (n=3, net positive).

---

## 5. Counterfactuals (binding gates)

Definition: eliminate entry if gate fires; `profit_saved` = −Σ(negative PnL removed); `profit_lost` = Σ(positive PnL removed); `net = saved − lost`.

### V1

| Gate | Elim | Win/Loss elim | Saved | Lost | **Net** | ROI after | Exp after | HR after |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SKIP | 15 | 6/8 | 98.01 | 101.44 | **−3.43** | 3.86% | 29.34 | 20% |
| PPG PROTECT | 10 | 5/5 | 63.26 | 193.01 | **−129.75** | 0.44% | 2.04 | 30% |
| 7D_NEG | 4 | 1/3 | 42.10 | 34.87 | **+7.23** | 1.84% | 9.84 | 37.5% |
| SKIP+PPG | 7 | 2/5 | 63.26 | 56.89 | **+6.37** | 2.15% | 12.04 | 23.1% |
| SKIP+FC / ALL3 | 4 | 1/3 | 42.10 | 34.87 | **+7.23** | 1.84% | 9.84 | 37.5% |

### V2

| Gate | Elim | Win/Loss elim | Saved | Lost | **Net** | ROI after | Exp after | HR after |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **SKIP** | 5 | 1/4 | 114.04 | 3.02 | **+111.02** | −0.08% | −0.40 | 10% |
| PPG PROTECT | 7 | 4/3 | 70.42 | 62.21 | +8.22 | −2.67% | −13.35 | 25% |
| 7D_NEG | 3 | 2/1 | 13.56 | 41.15 | **−27.59** | −2.38% | −11.89 | 25% |
| SKIP+PPG / SKIP+FC / ALL3 | 0 | — | 0 | 0 | 0 | — | — | — |

(V2 has **no overlap** of SKIP∩PROTECT or SKIP∩7D_NEG in this sample.)

### Combined V1+V2

| Gate | Elim | **Net** | ROI before→after | Exp before→after | HR before→after |
| --- | ---: | ---: | --- | --- | --- |
| **SKIP** | 20 | **+107.59** | 0.20% → **1.62%** | 1.00 → **9.51** | 37.1% → **13.3%** |
| PPG PROTECT | 17 | **−121.53** | 0.20% → −1.01% | worse | 37.1% → 27.8% |
| 7D_NEG | 7 | −20.36 | worse | worse | mild HR drop |
| SKIP+PPG | 7 | +6.37 | slight up | slight up | 37.1% → 21.4% |
| SKIP+FC / ALL3 | 4 | +7.23 | slight up | slight up | 37.1% → 29.0% |

**Capital utilization:** SKIP combined cuts deployed size 17,296 → 8,796 (−49%) while improving ROI/expectancy — classic quality-over-quantity.

---

## 6. Causality

**Does Decision Brain predict losses, or does Hard Risk only confirm what DB knew?**

**Both — sequenced:**

1. At entry, DB=`SKIP` already marks elevated risk (V1 loss-rate lift 2.67×; V2 SKIP loss 80%).  
2. BUY still executes (non-binding).  
3. Hard Risk later crystallizes a large share of those SKIP entries (V1 SKIP HR% = 60%).

So Hard Risk **confirms** a vulnerability Decision Brain had already flagged; it is not an independent root surprise. The causal failure remains **non-binding SKIP at entry**.

---

## 7. Learning chain

```
Learning tags / outcomes
    ↓
Decision Delta     ← BREAK (TESTING, ACTIVE=[], influence_delta=0)
    ↓
Decision Authority (SKIP produced but advisory)
    ↓
BUY (STRONG BUY / OPEN_VALID still authorized)
```

Unchanged from prior audit: learning does not alter entry authority.

---

## 8. V2 Score 100 vs 80 — explanation

| Hypothesis | Verdict in this sample |
| --- | --- |
| Score overconfident at 100 | **Supported** — 75% loss rate, 37.5% HR, avg −$14.77 vs score80 +$0.45 / 0% HR |
| Missing filters at OPEN | **Supported** — OPEN_VALID_CANDIDATE with score100 bypasses DB SKIP (3/3 CRITICAL had SKIP or PROTECT mem) |
| ADD never enters | **Supported** — all cycles tranche_count=1; cannot average; thin book amplifies path dependency but does not create the 100-vs-80 split alone |
| Conflict with Hard Risk | **Partial** — CRITICAL crystallizes score100 losers; score80 never hit CRITICAL here |
| Small sample only | **Also true** — n=8 vs 7; directionally consistent but not large-N proof |

**Conclusion:** Score100 is a **real severity marker** in this window, interacting with weak entry gates; treat as **soft threshold / research gate**, not sole hard law yet.

---

## 9. Required answers

### 1. Is Decision Brain SKIP a statistical predictor of loss?

**YES.** V1: loss% 53.3 vs 20.0 (lift 2.67). V2: loss% 80 on SKIP opens. Combined SKIP gate net **+$107.59**.

### 2. Is PPG PROTECT a predictor?

**Of Hard Risk rate on V1 — yes (70% HR).** Of economic benefit as hard eliminate — **NO** (combined net −$121.53). Predicts *conflicted* books (both big wins open and HR paths).

### 3. Is Forecast 7D NEGATIVE a predictor?

**Of HR path on V1 — yes (100% HR, n=4).** Of global economic hard gate — **weak/mixed** (V1 net +7.23; V2 net −27.59). Not the strongest global lever.

### 4. Highest predictive power?

**Decision Brain SKIP** (loss-rate lift + combined economic net + V2 dominance).  
Runner-up severity marker: **V2 score=100**.  
PPG / 7D_NEG: secondary / context features.

### 5. Hard / soft / bias / none?

| Signal | Recommendation |
| --- | --- |
| **Decision Brain SKIP** | **Hard gate candidate** (especially V2; globally proven on combined). On V1, prefer hard gate **with open-winner carve-out research** or start as **strong soft gate / veto bias** then promote. |
| **PPG PROTECT** | **Soft bias / veto weight only** — not hard eliminate |
| **7D_NEG** | **Soft bias** (or conjunctive with SKIP) — not standalone hard gate |
| **Score ≥ 100 (V2)** | **Soft threshold / dual confirmation** with SKIP |

### 6. Net economic impact (best proven gate)

**Binding SKIP on V1+V2 combined: +$107.59 net**, ROI 0.20%→1.62%, expectancy 1.00→9.51, HR 37%→13%.  
V2 alone: **+$111.02**.  
V1 alone unconditional SKIP: **≈$0 / −$3.43** (quality up, absolute flat).

---

## 10. Implication for next implementation sprint

Hypothesis from loss-cohort audit is **globally confirmed for SKIP as predictor and combined economic gate**, with important refinement:

- Do **not** hard-gate PPG PROTECT alone.  
- Do **not** assume V1-only SKIP hard gate is free of opportunity cost (open MTM winners).  
- First patch should target **binding Decision Brain SKIP** (scope: V2 first and/or global with measurement harness), optional conjunctive soft features (7D_NEG, score100), **not** PPG hard eliminate.

No code was changed in this sprint.

---

## Deliverables

- `tae_global_entry_gate_validation.json`  
- Canvas: `global-entry-gate-validation.canvas.tsx`

```
FINAL_VERDICT=GLOBAL_ENTRY_GATE_PROVEN
```

STOP.
