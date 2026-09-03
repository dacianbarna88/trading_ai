# TAE Economic Audit (READ-ONLY)

**Project:** TAE (Trading AI Engine)  
**Audit type:** ECONOMIC_READ_ONLY  
**Generated:** from live repository evidence (no code changes, no synthetic fills, no resets)  
**Twin:** `tae_economic_audit.json`  
**Final verdict:** `TAE_FIRST_ECONOMIC_BLOCKER_IDENTIFIED`

---

## 1. Executive Summary

TAE does **not** currently produce net PAPER profit on the canonical validation book.

| Metric (PAPER SSOT) | Value |
|---|---:|
| Validation capital base | **$30,000 USD** |
| Starting value (post `SYNTHETIC_100_FILL_DEFECT` reset) | **$30,340.92** |
| Ending equity (2026-07-31 daily equity) | **$29,673.79** |
| Realized PnL | **−$785.48** |
| Unrealized PnL | **+$118.35** |
| Net vs starting value | **−$667.13** (−2.20%) |
| Completed-cycle expectancy (n=7) | **−$50.38** |
| Completed-cycle win rate | **0%** |
| Hard-risk SELL realized sum | **−$900.67** (13 fills) |
| Non-hard-risk exitish realized sum | **+$66.44** |
| Capital utilization (last) | **42.4%** (idle cash ≈ $17,082) |

**First economic blocker:** `HARD_RISK_EXIT_LOSS_CRYSTALLIZATION`  
**Cause:** adverse / stop-cluster entries are authorized at high scores, then closed by fill-time hard risk (−3%/−5%) before trailing can contribute.  
**Recommended sprint (not implemented):** `PAPER_STOP_CLUSTER_ENTRY_PREVENTION_REUSE` — reuse existing ticker/stop-reentry gates; **do not** weaken hard-risk thresholds.

LIVE accounting and parallel V1/V2 books were inventoried but **excluded** from the clean economic universe (separate SSOTs; V1/V2 = `DATASETS_NOT_COMPARABLE_BY_DESIGN`).

---

## 2. Scope and Methodology

1. **AUDIT FIRST / READ-ONLY** — no patches, commits, resets, or synthetic trades.  
2. Universe = **ECONOMIC_REAL_PAPER** only (`runtime_outputs/paper_execution/*`).  
3. Explicitly excluded: LIVE `tae_accounting_snapshot.json`, `parallel_paper/v1|v2`, SHADOW sizing-only, non-reproducible REPLAY claims, SYNTHETIC fixtures, unit-test portfolios.  
4. Status taxonomy: EXISTS / ACTIVE / WIRED / EXISTS_NOT_WIRED / DUPLICATE / TRUE_GAP / INSUFFICIENT_EVIDENCE.  
5. No TRUE_GAP declared when the function exists under another name.  
6. Observation ≠ evidence ≠ interpretation ≠ counterfactual; confidence labeled.

---

## 3. Evidence Inventory

| Artifact | Role |
|---|---|
| `PROJECT_BOOK.md` / `SESSION_START.md` | Governance, SSOT rules, Phase X |
| `runtime_outputs/paper_execution/paper_portfolio.json` | PAPER book SSOT |
| `runtime_outputs/paper_execution/paper_trades.jsonl` | Fill SSOT |
| `runtime_outputs/paper_execution/paper_orders.jsonl` | Authorization / blocks |
| `runtime_outputs/paper_execution/paper_daily_equity.jsonl` | Equity / DD / utilization |
| `runtime_outputs/paper_execution/mark_to_market.json` | MTM duplicate view |
| `tae_canonical_economic_baseline_2026_07_29.json` | Capital + completed-cycle stats |
| `tae_canonical_profitability_attribution_2026_07_29.json` | Ranked economic leaks |
| `runtime_outputs/longitudinal_memory/hard_risk_post_exit.json` | Post-exit follow-ups |
| `runtime_outputs/learning_economic_attribution/summary.json` | Learning economic effect |
| `TAE_ECONOMIC_ROI_MASTER_REPORT.md` | Wiring-gap ROI ranking (2026-07-15) |
| `tae_accounting_snapshot.json` | LIVE SSOT (excluded from PAPER metrics) |
| `runtime_outputs/parallel_paper/{v1,v2}` | Parallel arms (excluded; non-comparable) |

---

## 4. Economic Dataset Integrity

| Measure | Value |
|---|---:|
| Raw trade events | 50 |
| Unique trade keys | 50 |
| Duplicate journal events | 0 |
| Deduplicated economic trades | 50 |
| BUY_PAPER | 20 |
| SELL_PAPER | 15 |
| REDUCE_PAPER | 10 |
| PROTECT_PAPER | 4 |
| ROTATE_PAPER | 1 |
| Open positions | 14 |
| Orders raw | 1612 (NO_CHANGE 1460; EXECUTED 66) |
| Period | 2026-07-08 → 2026-07-31 |
| Capital base | $30,000 USD |
| Reporting currency | USD |
| Last equity recon | PASS |

**Class mix used:** ECONOMIC_REAL_PAPER only. SHADOW/REPLAY/LIVE/V1/V2/SYNTHETIC not summed into primary PnL.

---

## 5. Canonical Economic SSOT Map

| Metric family | Canonical SSOT | Duplicates / notes |
|---|---|---|
| PAPER equity / cash / PnL | `paper_portfolio.json` | `mark_to_market.json`, daily equity — must agree; do not merge LIVE |
| Fills | `paper_trades.jsonl` | Orders EXECUTED subset |
| Equity curve | `paper_daily_equity.jsonl` | Append-only |
| Validation capital | baseline JSON `validation_capital_base=30000` | `starting_value_recorded=30340.92` is post-reset book |
| Cycle expectancy | baseline `completed_cycle_stats` | n=7 insufficient |
| Leak ranking | attribution `top_economic_leaks` | — |
| Hard-risk aftermath | `hard_risk_post_exit.json` | Mostly INVALID_DATA |
| LIVE AV | `tae_accounting_snapshot.json` | **Different book** |

---

## 6. Component Audit Table

See machine-readable `component_audit` in `tae_economic_audit.json` for full columns. Summary:

| COMPONENT | STATUS | ECONOMIC NOTE |
|---|---|---|
| PDE / Decision Brain | EXISTS_ACTIVE_WIRED | Actions fire; cycle win_rate 0 |
| Paper Execution | EXISTS_ACTIVE_WIRED | Integrity OK |
| Fill-time Hard Risk | EXISTS_ACTIVE_WIRED | Dominant closed-loss realizer (−$900.67) |
| Profit Trailing | EXISTS_ACTIVE_PARTIALLY_WIRED | 0 trailing exits |
| PTA trim sizing | EXISTS_NOT_WIRED | Execution ignores suggested trim % |
| Adaptive deployment gates | EXISTS_ACTIVE_WIRED | 45+24 BUY blocks |
| Learning runtime | EXISTS_ACTIVE_PARTIALLY_WIRED | No matured economic impact |
| Sizing CF replay | EXISTS_ACTIVE_PARTIALLY_WIRED | Shadow / not fill-driving |
| Profit attribution | EXISTS_ACTIVE_WIRED | Identifies #1 leak |
| Daily paper equity | EXISTS_ACTIVE_WIRED | DD 2.20% |
| LIVE accounting | EXISTS_ACTIVE_WIRED | Excluded DUPLICATE book |
| Full MFE/MAE analytics | INSUFFICIENT_EVIDENCE | MFE null; followups invalid |

No unjustified TRUE_GAP for hard risk, trailing, PDE, or attribution — they exist.

---

## 7. Economic Funnel

```
MARKET DATA → DECISION → AUTHORIZED → EXECUTION → FILLED → MANAGED → EXIT → SETTLEMENT/ACCOUNTING → LEARNING → NEXT
```

| Transition | Volume / note | Economic effect |
|---|---|---|
| Decision → order | Heavy NO_CHANGE (1460/1612) | Low action rate |
| Authorized → blocked | 45 ticker-scope + 24 capital-cap | Prevention exists; incomplete vs historical cluster losses |
| Fill BUY | 20 | Capital deployed |
| Managed → EXIT | HR sells 13 vs other exitish 16 | **HR crystallizes −$900.67**; other exitish **+$66.44** |
| Learning → next | flips exist; matured impact 0 | No proven expectancy lift |

**First demonstrable economic degradation:** after fill, paths that hit hard risk realize large closed losses; this dominates all other exit economics.

---

## 8. Profit Sources

1. Non-hard-risk REDUCE/PROTECT-style realized ≈ **+$66.44**  
2. Open unrealized ≈ **+$118.35**  
Neither offsets hard-risk crystallization.

---

## 9. Loss Sources

1. **Hard-risk SELL crystallization** ≈ **−$900.67** (13)  
2. **Completed cycles** ≈ **−$352.66** (7 cycles, 0 wins)  
3. **Stop-cluster concentration** (attribution) ≈ **−$308.5** (MU/AMAT focus)

---

## 10. Entry Quality

- **Observation:** HARD_RISK exits carry `entry_score=0.95` on multiple names (AMAT, MU, SIE.DE, …).  
- **Evidence:** `hard_risk_post_exit.json`; trade reasons show −3% to −6% stops.  
- **Interpretation:** High score ≠ positive expectancy in this sample; adverse entry into stop-cluster names is upstream of crystallization.  
- Stratified score buckets: **INSUFFICIENT_EVIDENCE** (n too small).

---

## 11. Exit Quality

| Exit class | n | Realized sum |
|---|---:|---:|
| HARD RISK SELL | 13 | −900.67 |
| Other exitish (REDUCE/PROTECT/non-HR SELL) | 16 | +66.44 |
| Trailing exits | 0 | 0 |

Trailing cannot be blamed as the primary loss source; it has not yet produced exits.

---

## 12. Risk Economic Impact

- Hard risk is **fully wired** and **economically consequential**.  
- Proven losses avoided / profits removed / recovery-after-stop: **INSUFFICIENT_EVIDENCE** (follow-ups INVALID_DATA/PENDING).  
- Attribution itself recommends **not** changing hard-risk thresholds in the next controlled intervention — focus entry filter / pre-stop behavior.

---

## 13. Sizing Economic Impact

- PTA emits `suggested_partial_size_pct`; execution hardcodes trim 20/30%.  
- Status: **EXISTS_NOT_WIRED**.  
- Economically secondary to hard-risk closed losses (ROI master bounded upside, not the −$900 sink).

---

## 14. Trailing Economic Impact

- Contract exists (+5%/−2%); some open lots `profit_trailing_active=true`.  
- **0 trailing exits** in journal → contribution **$0** observed.  
- Leak #3: `PROFIT_TRAILING_NOT_YET_ECONOMICALLY_OBSERVABLE`.

---

## 15. Portfolio and Capital Utilization

- Utilization last **42.4%**; idle cash **~$17.1k**.  
- 24 BUY blocks for capital cap — capital scarcity is real for some candidates, but **not** the first closed-loss driver.  
- Open book: 14 names; historical damage concentrated in a small stop-cluster set.

---

## 16. Opportunity Cost

- Legacy GII meter **$829.72** (ROI master 2026-07-15) — not recomputed here.  
- Whether blocked BUYs were +EV: **INSUFFICIENT_EVIDENCE**.

---

## 17. Re-buy Analysis

- `STOP_REENTRY_CHURN` appears in rule_sources.  
- Economic proof of re-buy harm/help: **INSUFFICIENT_EVIDENCE**.

---

## 18. Regime Analysis

- `market_regime` on hard-risk exits: **UNKNOWN**.  
- Status: **INSUFFICIENT_EVIDENCE**.

---

## 19. Learning and Adaptive Behaviour

| Class | Result |
|---|---|
| Classification | `LEARNING_ACTIVE_NO_PROVEN_ECONOMIC_EFFECT` |
| Technical | `LEARNING_ECONOMIC_ATTRIBUTION_CLOSED` |
| Economic | `LEARNING_VALUE_INCONCLUSIVE_INSUFFICIENT_SAMPLE` |
| Matured impact decisions | 0 |
| Action flips | 15 |
| Provisional net | −9.8 (insufficient) |

Learning runs; **downstream profit improvement is unproven**.

---

## 20. Replay and Historical Evidence

- Sizing CF replay / shadow sizing: observability.  
- Large replay protection claims rejected historically as non-reproducible (`REPLAY_VALUE_NOT_REPRODUCIBLE` in ROI master).  
- Used only conservative leave-one-out / attribution figures for counterfactual.

---

## 21. Paper Trading Performance

Canonical PAPER is the only promotion-relevant economic book for this audit. Result: **negative net**, **zero completed-cycle wins**, hard-risk dominated.

---

## 22. Accounting Reconciliation

- Last `paper_daily_equity` `reconciliation_status=PASS`, `reconciliation_delta=0`.  
- LIVE book separately OK at AV **$29,554.27** — **not merged**.

---

## 23. ROI / Expectancy / Drawdown / Win Rate

| Metric | Value |
|---|---:|
| ROI vs starting value | −2.20% |
| ROI vs $30k base | −1.09% |
| Expectancy / completed cycle | −$50.38 (n=7) |
| Win rate | 0% |
| Profit factor | 0 |
| Max / current DD (equity peak path) | 2.20% / $667 |
| Annualized ROI | INSUFFICIENT_EVIDENCE |

---

## 24. Loss Distribution

- Largest completed-cycle loss: **−$163.10 (MU)**.  
- Average loss (completed): **−$58.78**; median **−$20.74**.  
- Hard-risk sell average ≈ **−$69.28**.  
- Tail: semiconductor / high-beta names dominate early HR exits.

---

## 25. Counterfactual Analysis

**Base:** completed-cycle net −352.66; expectancy −50.38; HR sells −900.67.

**Conservative:** avoid half of attribution stop-cluster impact (−308.5/2 = +154.25) → completed-cycle net ≈ −198.4; expectancy ≈ −28.3. Associative; LOW confidence.

**Evidence-bound upper:** MU+AMAT leave-one-out deltas ≈ +308.5 → completed-cycle net ≈ −44.2 — still not clearly profitable; does **not** assume threshold changes. LOW confidence.

---

## 26. Ranked Economic Blockers

1. `HARD_RISK_EXIT_LOSS_CRYSTALLIZATION` (−900.67, HIGH)  
2. `ADVERSE_ENTRY_INTO_STOP_CLUSTER_TICKERS` (−308.5, HIGH)  
3. `PTA_TRIM_SIZE_NOT_APPLIED_BY_EXECUTION` (EXISTS_NOT_WIRED, secondary)  
4. `PROFIT_TRAILING_NOT_YET_ECONOMICALLY_OBSERVABLE` ($0 observed)  
5. `LEARNING_NO_MATURED_ECONOMIC_EFFECT` ($0 matured)

---

## 27. First Economic Blocker

**Name:** `HARD_RISK_EXIT_LOSS_CRYSTALLIZATION`  

**Cause:** High-score PAPER entries enter adverse/stop-cluster paths and are exited by fill-time hard risk before trailing economics appear. Hard risk is the **realization mechanism** of closed losses; adverse entry is the **upstream selector**. Idle cash / trailing absence / learning are not the first dollar sink.

**Confidence:** HIGH (dollar magnitude + attribution causal tag + contrast vs +$66 non-HR exits).  
**Caveat:** Cannot prove hard risk is “too tight” — post-exit marks insufficient — therefore first sprint must **not** loosen −3/−5.

---

## 28. Existing Components and Wiring Status

Available without new engines:

- Hard risk (WIRED) — observe/keep  
- Adaptive `BLOCKED_TICKER_SCOPE` (WIRED) — extend reuse  
- `STOP_REENTRY_CHURN` rules (partially wired)  
- `hard_risk_post_exit` memory (WIRED observe)  
- Challenger guidance to avoid MU/AMAT (advisory / partial)  
- PTA trim (EXISTS_NOT_WIRED) — useful later, not first

---

## 29. Highest-Impact Economic Sprint

**Name:** `PAPER_STOP_CLUSTER_ENTRY_PREVENTION_REUSE`  

**Problem:** New BUYs into historically hard-stopped cluster names recreate crystallization losses.  

**Reuse:** adaptive ticker gates, stop-reentry LTB rules, post-exit memory, attribution leak list, existing PDE auth — **no new brain/model**.  

**Hypothesis:** Preventing those entries improves expectancy/ROI without touching SELL or hard-risk thresholds.  

**Impact (estimate only):** conservative +~$154 completed-cycle path; upper ~+$308 leave-one-out bound.  

**Gates:** PAPER_ONLY; no threshold change; no LIVE promotion; recon PASS; HR sell rate on cluster names declines.  

**Stop:** any threshold weakening without valid post-exit data; new parallel engine; merging LIVE+PAPER.

**Not implemented in this task.**

---

## 30. Limitations and Confidence

- n=7 completed cycles — statistically insufficient for fine claims  
- MFE/capture mostly missing  
- Post-exit follow-ups invalid/pending  
- GII opportunity cost dated  
- Pre-existing dirty git tree (unrelated); audit only added the two deliverables  

Overall blocker identification confidence: **HIGH**. Counterfactual magnitudes: **LOW**.

---

## 31. Final Answers

1. **Where profit?** Small non-HR realized + open unrealized — insufficient.  
2. **Where loss?** Hard-risk SELL crystallization and zero-win completed cycles.  
3. **First blocker?** `HARD_RISK_EXIT_LOSS_CRYSTALLIZATION`.  
4. **Cause?** Adverse/stop-cluster entries closed by hard risk pre-trailing.  
5. **Mechanism class?** Entry quality → hard risk realization (not idle cash first).  
6. **EXISTS_NOT_WIRED helpers?** PTA trim yes (secondary); stop-cluster prevention partially present.  
7. **First sprint?** `PAPER_STOP_CLUSTER_ENTRY_PREVENTION_REUSE` (identify only).

---

## 32. Final Verdict

**`TAE_FIRST_ECONOMIC_BLOCKER_IDENTIFIED`**

TAE is architecturally mature enough to measure economics. On the canonical PAPER book it is **not profitable**. The first economic blocker is hard-risk loss crystallization fed by adverse entries — address via **reuse of existing entry gates**, not via new engines and not via weakening hard risk until post-exit evidence matures.
