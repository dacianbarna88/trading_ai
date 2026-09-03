# TAE Economic Loss Decomposition

**Sprint:** `TAE_ECONOMIC_LOSS_DECOMPOSITION`  
**Mode:** READ_ONLY | PAPER_ONLY | NO_CODE_CHANGE  
**Generated:** 2026-08-03  
**Sources:** `paper_execution` journals + MTM (V1), `parallel_paper/v2` portfolio / cycle_state / trades / decisions (V2)

## FINAL_VERDICT

**`TAE_PRIMARY_ECONOMIC_LOSS_SOURCE_IDENTIFIED`**

Primary shared economic loss source: **Hard-Risk forced exit crystallization** — protective sells lock mark-to-market drawdowns into realized losses before mean-reversion / thesis completion, with win/loss asymmetry that the current expectancy cannot overcome.

---

## 1. Strategy scoreboard (calculated)

| Metric | V1 | V2 |
| --- | ---: | ---: |
| Capital base | 30,000.00 | 30,000.00 |
| Equity | 29,729.32 | 29,884.95 |
| Cash | 21,235.78 | 24,952.32 |
| Invested | 8,493.53 | 4,932.63 |
| Capital utilization | **28.31%** | **16.44%** |
| Idle cash / base | **70.79%** | **83.17%** |
| ROI vs base | **−0.9023%** | **−0.3835%** |
| Realized PnL | −765.57 | −47.68 |
| Unrealized PnL | +153.97 | −67.37 |
| Total PnL (R+U) | **−611.60** | **−115.05** |
| Closed trades (SELL/CLOSE) | 21 | 5 cycles closed |
| Win rate (closed) | **23.81%** (5/21) | **40.00%** (2/5) |
| Avg win | +19.37 | +29.74 |
| Avg loss | **−63.65** | **−35.72** |
| Median win | +22.02 | +29.74 |
| Median loss | −39.69 | −29.59 |
| Best trade | +34.87 (MRK) | +36.05 (ULVR.L trailing) |
| Worst trade | **−163.10 (MU, HR critical)** | **−51.57 (MSFT, HR critical)** |
| Expectancy / closed trade | **−40.86** | **−9.54** |
| Profit factor | **0.1014** | **0.5551** |
| Max equity DD (V1 daily equity) | 0.71% | n/a (short equity series) |

**Asymmetry (V1):** |avg loss| / avg win = **3.29×**. Profit factor < 0.11 ⇒ winners cannot fund losers.

---

## 2. V1 — closed-trade loss anatomy (USD + %)

Ground truth for exit class = executed `paper_orders.jsonl.reason` joined to `paper_trades.jsonl` by `decision_id`.

**Gross closed-loss pool** = sum of negative realized sells = **−$954.8125**  
(Positive closed sells = +$96.8577; journal net closed = −$857.9548; portfolio `realized_pnl` = −$765.5725 ⇒ reconciliation delta +$92.38 reserved as accounting residue, not reassigned.)

### Calculated decomposition of gross closed losses (−$954.81 = 100%)

| Loss source | USD | % of gross closed losses | n |
| --- | ---: | ---: | ---: |
| **Hard Risk STOP −3%** (`HARD_STOP_LOSS_-3`) | **−472.89** | **49.53%** | 10 |
| **Hard Risk CRITICAL −5%** (`HARD_CRITICAL_STOP_-5`) | **−261.48** | **27.39%** | 2 |
| **Trailing loss exits** (`PROFIT_TRAILING_*` with pnl&lt;0) | **−220.44** | **23.09%** | 4 |
| **Hard Risk combined** | **−734.37** | **76.91%** | 12 |

Trailing exits overall (incl. winners): n=9, net **−$123.58** (losses −220.44, wins +96.86).

### Immediate stop-out subset (entry timing inside Hard Risk)

Where FIFO entry timestamp exists and hold &lt; 1 day:

| Ticker | Hold (days) | Exit class | Realized |
| --- | ---: | --- | ---: |
| MU | 0.013 | HARD_RISK_CRITICAL | −163.10 |
| AMAT | 0.013 | HARD_RISK_STOP | −122.41 |

**Immediate HR stop-outs = −$285.51 = 29.90% of gross closed-loss pool.**  
These are calculated entry-quality failures that Hard Risk then crystallized within hours.

### V1 total PnL bridge (−$611.60)

| Component | USD | Notes |
| --- | ---: | --- |
| Portfolio realized | −765.57 | SSOT on portfolio |
| Open unrealized (MTM) | +153.97 | Offsets part of hole |
| **Total PnL** | **−611.60** | Identity R+U |

Open book is **net helpful** for V1 (+153.97). The economic hole is almost entirely **realized exit crystallization**, not open MTM.

---

## 3. V2 — cycle / tranche / unrealized anatomy

### Closed cycles (cycle_state SSOT)

| Ticker | Close reason | Realized | Tranches |
| --- | --- | ---: | ---: |
| MSFT | `CLOSE_HARD_RISK_CRITICAL` | −51.57 | 1 |
| NVDA | `CLOSE_HARD_RISK_CRITICAL` | −25.99 | 1 |
| SAP.DE | `CLOSE_HARD_RISK_CRITICAL` | −29.59 | 1 |
| PM | `V2_PROFIT_TRAILING_5_2` | +23.44 | 1 |
| ULVR.L | `V2_PROFIT_TRAILING_5_2` | +36.05 | 1 |
| **Net realized** | | **−47.68** | |

Gross realized losses (all Hard Risk Critical) = **−$107.16**  
Gross realized wins (all trailing) = **+$59.48**

### Open unrealized (current marks)

| Side | USD |
| --- | ---: |
| Unrealized losses (LLY, ABBV, MRK, PG, AIR.PA, HD) | **−96.56** |
| Unrealized gains (SIE.DE, DIA, GE, ALV.DE) | **+29.18** |
| Net unrealized | **−67.37** |

### Calculated V2 loss pool (negative contributors only)

| Loss source | USD | % of loss pool |
| --- | ---: | ---: |
| **Hard Risk Critical closed** | **107.16** | **52.60%** |
| **Open unrealized drawdown** | **96.56** | **47.40%** |
| **Pool total** | **203.72** | **100%** |

Identity check: −107.16 + 59.48 − 96.56 + 29.18 = **−115.05** (= total PnL).

### Tranche / ADD / capital utilization (calculated)

- Company budget / cycle = **$2,500**; first tranche fill ≈ **$500** (20%).
- All **10** open cycles: `tranche_count=1`, status `ACCUMULATION_STOPPED`, budget_remaining ≈ **$2,000** each.
- Unused open-cycle tranche budget = **10 × ~2000 = $20,000.00**.
- Decision reason counts (full V2 journal): `HOLD_PRICE_STEP_NOT_REACHED` **2149**, `STOP_CYCLE_STATE` **185**, `V2_HOLD_OPEN` **2894**.
- **Zero ADD fills** in execution journal (OPEN 15, CLOSE 3 executed rows; profitable PM/ULVR closes present in trades/cycles).

V2 is not losing primarily from overtrading — it loses from **Hard Risk on thin first tranches** plus **open drawdown without ADD averaging**, while **83% cash idle**.

**Idle-cash note (calculated, not a PnL %):** invested ROI = −115.05 / 4932.63 = **−2.332%**. Scaling that ROI to full 30k would imply **−$699.73** total PnL. Idle cash therefore **reduced absolute USD loss** under negative expectancy; it is a utilization / upside-capture defect, not the primary loss source in the current sample.

---

## 4. Position-level ledger (V1 closed)

| ticker | exit class | realized | hold_d | notes |
| --- | --- | ---: | ---: | --- |
| MU | HR_CRITICAL | −163.10 | 0.01 | immediate critical stop |
| SIE.DE | HR_STOP | −142.49 | — | large −3% crystallization |
| AMAT | HR_STOP | −122.41 | 0.01 | immediate stop |
| MC.PA | HR_CRITICAL | −98.38 | — | critical −5% |
| LLY | HR_STOP | −94.15 | — | |
| MRK | TRAILING | −93.57 | — | trailing loss exit |
| PM | TRAILING | −87.18 | — | trailing loss exit |
| AAPL | TRAILING | −39.69 | — | trailing loss exit |
| AMAT | HR_STOP | −22.99 | 0.94 | |
| GE | HR_STOP | −21.84 | 19.60 | |
| NVDA | HR_STOP | −18.50 | 3.09 | PROTECT→SELL path |
| LLY | HR_STOP | −14.46 | 19.98 | |
| SIE.DE | HR_STOP | −13.62 | 2.70 | |
| GE | HR_STOP | −12.00 | 6.69 | REDUCE→SELL |
| QQQ | HR_STOP | −10.43 | — | PROTECT→SELL |
| HD | TRAILING | 0.00 | 0.31 | flat trailing |
| ABBV | TRAILING | +0.84 | 20.05 | |
| ULVR.L | TRAILING | +16.33 | 20.36 | |
| PM | TRAILING | +22.02 | 18.95 | |
| AIR.PA | TRAILING | +22.80 | 21.53 | |
| MRK | TRAILING | +34.87 | 19.98 | best V1 |

Avg hold (where measurable) = **11.02 days**.

### V1 open positions (MTM)

| ticker | invested | upnl | upnl% | run-up% | sector |
| --- | ---: | ---: | ---: | ---: | --- |
| SPY | 2555.91 | +21.87 | +0.86 | 0.86 | ETF_US |
| PG | 1985.59 | −36.78 | −1.85 | 2.80 | STAPLES |
| SAP.DE | 1000.71 | +88.38 | +8.83 | 8.83 | TECH |
| SIE.DE | 942.10 | +43.35 | +4.60 | 4.60 | INDUSTRIAL |
| ALV.DE | 757.29 | +4.40 | +0.58 | 0.58 | FINANCIAL |
| DIA | 417.40 | +4.58 | +1.10 | 1.10 | ETF_US |
| SHEL.L | 376.71 | +28.18 | +7.48 | 7.48 | ENERGY |
| HD | 303.87 | 0.00 | 0.00 | 3.24 | DISCRETIONARY |

Concentration: top 2 names (SPY+PG) = **54.46%** of invested; HHI = **0.1919**.

---

## 5. Position-level ledger (V2 open + closed)

### Open (peak from cycle_state.highest_price)

| ticker | avg | peak | mark | pnl% | dd from peak% | upnl | tranches | budget_rem |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LLY | 1192.17 | 1230.91 | 1118.57 | −6.17 | −9.13 | −30.87 | 1 | ~2000 |
| ABBV | 261.01 | 267.35 | 247.01 | −5.36 | −7.61 | −26.82 | 1 | ~2000 |
| MRK | 131.98 | 134.93 | 127.53 | −3.37 | −5.48 | −16.86 | 1 | ~2000 |
| PG | 148.56 | 153.43 | 144.53 | −2.71 | −5.80 | −13.56 | 1 | ~2000 |
| AIR.PA | 210.55 | 212.90 | 208.00 | −1.21 | −2.30 | −6.06 | 1 | ~2000 |
| HD | 338.77 | 348.79 | 337.15 | −0.48 | −3.34 | −2.39 | 1 | ~2000 |
| ALV.DE | 430.30 | 434.50 | 432.90 | +0.60 | −0.37 | +3.02 | 1 | ~2000 |
| GE | 362.08 | 365.80 | 365.78 | +1.02 | −0.01 | +5.11 | 1 | ~2000 |
| DIA | 524.14 | 530.41 | 530.21 | +1.16 | −0.04 | +5.79 | 1 | ~2000 |
| SIE.DE | 276.85 | 285.50 | 285.30 | +3.05 | −0.07 | +15.26 | 1 | ~2000 |

Hard risk active on open book? Marks show several names near/through −3%/−5% informational bands; V2 adapter treats price drawdown as **informational during accumulation** (no FORCE close on −3% while accumulating). Current open losses sit in unrealized, not yet crystallized — except prior CRITICAL closes.

---

## 6. Dimension coverage (measured)

| Dimension | V1 finding | V2 finding |
| --- | --- | --- |
| ENTRY QUALITY | Immediate HR stop-outs 29.90% of closed losses | OPEN_VALID_CANDIDATE then CRITICAL on MSFT/NVDA/SAP |
| EXIT QUALITY | Forced HR / trailing dominate; soft HOLD rarely survives | Trailing captures winners; CRITICAL locks losers |
| HARD RISK | **76.91% of closed losses** | **52.60% of loss pool** (closed CRITICAL) |
| TRAILING | 23.09% of closed losses; also source of all V1 wins | Source of both V2 wins (PM, ULVR) |
| TARGET EXIT | Not primary in this sample | Not observed as close_reason |
| HOLD | Paper orders: HOLD 486 vs SELL 35 — but sells over-represent PnL | HOLD_PRICE_STEP 2149 blocks ADD |
| REBUY | Present in V2 policy; watch blocked often | REENTRY blocks counted; no material economic rescue |
| TRANCHE | N/A (V1 full-size entries) | **100% open cycles stopped after tranche 1** |
| POSITION SIZING | Full paper buys → larger HR USD | Thin 500$ tranches → smaller USD / worse util |
| MARKET REGIME | Horizon fields on decisions; not sole driver of closed losses | MARKET_CLOSED 1250 decisions — timing friction |
| PORTFOLIO ALLOCATION | ETF+staples heavy | Diversified 10 names × ~500$ |
| CAPITAL UTILIZATION | 28.31% | 16.44% |
| IDLE CASH | 70.79% of base | 83.17% of base |
| TICKER CONCENTRATION | SPY+PG 54% invested | Flat ~500$/name |
| HOLDING TIME | avg ~11d closed | CRITICAL closes in hours–days; winners 1–2d trailing |
| EXPECTANCY | −40.86 / closed | −9.54 / closed cycle |
| LEARNING | Rules TESTING; influence_delta≈0 on loss drivers | 1 learning event (SAP CLOSE); no V1 contamination |

---

## 7. Counterfactuals (calculated)

### V1

| Counterfactual | Method | Equity | ROI vs 30k | Δ equity |
| --- | --- | ---: | ---: | ---: |
| Baseline | current | 29,729.32 | −0.90% | — |
| **No Hard Risk crystallizations** | equity − Σ(HR realized losses) = +734.37 | **30,463.69** | **+1.55%** | **+734.37** |
| No trailing *loss* exits | +220.44 | 29,949.76 | −0.17% | +220.44 |
| Keep trailing wins only effect | already in baseline | — | — | — |

Expectancy if HR loss trades removed from closed set: remaining 9 trailing-dominated outcomes net −123.58 / 9 ≈ **−13.73** (still negative but far less than −40.86).

Drawdown: current equity DD 0.71% (path). Removing HR would also remove the largest single-day crystallizations (MU/AMAT cluster 2026-07-08).

Capital utilization unchanged in these CFs (exits removed ≠ redeployed).

### V2

| Counterfactual | Method | Equity | ROI | Δ |
| --- | --- | ---: | ---: | ---: |
| Baseline | current | 29,884.95 | −0.38% | — |
| **No CRITICAL closes** | +107.16 | **29,992.11** | **−0.03%** | **+107.16** |
| No open unrealized losses | +96.56 | 29,981.51 | −0.06% | +96.56 |
| Idle cash @ same invested ROI | scales loss to −699.73 if fully invested | worse | — | idle **mitigates** USD loss while expectancy &lt; 0 |

---

## 8. Learning — observed vs economic effect

| Check | Evidence | Verdict |
| --- | --- | --- |
| Observed problem? | Rule attribution + lifecycle track MISSED_PROFIT_PROTECTION, STOP_REENTRY_CHURN, etc. | **YES — recorded** |
| Changed decision? | All major rules remain `TESTING`; `ACTIVE`/`TRUSTED` = empty; `recommended_influence_delta` = **0.0** on loss-dominant rules | **NO material decision change** |
| Economic effect? | Attribution `net_pnl_impact` mirrored across many rules (~+$138) on BUY_PAPER samples — **not** causal on Hard Risk sells; influence_multiplier 0.85 only | **NO proven loss reduction** |
| V2 learning | 1 `EXECUTION_OUTCOME` for SAP CLOSE_HARD_RISK_CRITICAL | **Logged only** |

**Conclusion:** Learning is in **observe/register** mode, not in **economically corrective** mode for the primary loss source.

---

## 9. Answers (required)

### 1. Why does V1 lose?

Because **Hard Risk forced sells crystallize drawdowns** (76.91% of closed losses), with catastrophic asymmetry (avg loss 3.3× avg win) and a non-trivial **immediate stop-out** cluster (29.90%). Trailing contributes additional locked losses (23.09%) while capturing only small wins. Open MTM (+154) is not the problem.

### 2. Why does V2 lose?

Because **Hard Risk Critical closes** on first-tranche positions (52.60% of loss pool) plus **open unrealized drawdowns** without ADD (47.40%). Trailing works when it fires (PM/ULVR). Capital stays mostly idle; ADD is blocked (`HOLD_PRICE_STEP_NOT_REACHED` / `STOP_CYCLE_STATE`).

### 3. Same cause?

**Yes on the primary axis:** protective Hard Risk crystallization of adverse marks.  
**No on the secondary axis:** V1 also bleeds via trailing loss exits at full size; V2 bleeds via open unrealized + aborted tranche ADD while keeping cash idle.

### 4. First economic blocker

**Hard Risk exit crystallization** (V1 −3%/−5% forced sells; V2 CRITICAL closes).

### 5. Second

**V1:** Trailing exits that realize losses (and tiny wins).  
**V2:** Open unrealized drawdown with **no ADD** (tranche stopped after 1).

### 6. Third

**Expectancy / payoff asymmetry** (V1 profit factor 0.10) amplified by **low capital utilization** that limits recovery capacity when winners appear (structural, not the USD primary).

### 7. Existing components that control each blocker

| Blocker | Existing controller |
| --- | --- |
| Hard Risk crystallization | `hard_risk_guardian` + PAPER adapter / V2 `tae_strategy_v2_hard_risk_adapter` |
| Trailing exits | LIVE/PAPER trailing path; V2 `tae_strategy_v2_trailing` + exit policy |
| ADD / tranche | `tae_strategy_v2_buy_policy` (price step), cycle foundation STOP_ACCUMULATION |
| Sizing / utilization | V2 tranche_fraction / company_budget; V1 paper execution sizing |
| Learning influence | CLR + `rule_lifecycle` / `rule_outcome_attribution` (currently TESTING) |

### 8. Built but underused?

**Yes.**

- V2 **ADD / tranche budget ($20k unused)** — logic exists; price-step + STOP_ACCUMULATION prevent use.
- V2 **reentry after trailing** — policy present; little economic rescue in sample.
- **Learning lifecycle** — observes MISSED_PROFIT_PROTECTION / stop churn but does not promote rules to ACTIVE with nonzero influence on Hard Risk outcomes.
- V1 **PROTECT/HOLD** soft paths are frequently overridden by Hard Risk (by design) — soft logic is underpowered relative to guardian.

### 9. First economic sprint with maximum impact (analysis-only recommendation)

**Hard-Risk crystallization vs hold-to-thesis measurement sprint** — quantify, on the existing PAPER books only, the counterfactual equity path if −3% STOP sells had been deferred to trailing/thesis exits (no code change in that sprint beyond measurement harness if later authorized). This targets the **76.91% (V1) / 52.60% (V2)** calculated loss pools.

Not V3. Not new models. Not BUY/SELL/HR/sizing/trailing edits in *this* sprint (none were made).

---

## 10. Expanded loss % view (reporting format requested)

### V1 — gross closed-loss pool (−$954.81)

```
Hard Risk STOP (−3%)     49.53%   (−$472.89)
Hard Risk CRITICAL (−5%) 27.39%   (−$261.48)
Trailing loss exits      23.09%   (−$220.44)
────────────────────────────────────────────
Total                    100.00%  (−$954.81)

of which immediate HR stop-outs (<1d hold): 29.90% (−$285.51)  [subset of Hard Risk]
```

### V2 — negative contributor pool (−$203.72)

```
Hard Risk CRITICAL closed  52.60%  (−$107.16)
Open unrealized drawdown   47.40%  (−$96.56)
────────────────────────────────────────────
Total                     100.00%  (−$203.72)

Trailing wins (offset, not a loss source): +$59.48
Idle cash share of base (structural):        83.17%  [not a PnL %]
```

---

## Artifacts

- `tae_economic_loss_decomposition.json` — machine-readable twin of this report  
- Canvas: `economic-loss-decomposition.canvas.tsx` (visual scoreboard)

**NO CODE CHANGES were made to BUY, SELL, Hard Risk, sizing, or trailing in this sprint.**

STOP.
