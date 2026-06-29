# TAE X.9 Pre-Audit — Existing Shadow Mode Validation

**Date:** 2026-06-29  
**Mode:** AUDIT ONLY — no implementation, no `live_bot.py` changes  
**Question:** Does the project already measure TAE impact on LIVE decisions after X.8 integration?

---

## 1. VERDICT

### **`DOES_NOT_EXIST`**

There is **no canonical module** that implements X.9 Shadow Mode Validation as defined (structured per-BUY event log, blocked-vs-allowed outcome comparison, `tae_shadow_validation.json` / report, connected to the X.8 `RISK_ADVISORY` risk gate).

**Secondary classification:** adjacent capabilities exist as **`EXISTS_PARTIAL`** (see §3–§4). None qualify as canonical X.9.

---

## 2. Context reviewed (mandatory)

| Document | Relevant finding |
|----------|------------------|
| `SESSION_START.md` | Explicitly states: *"Shadow validation stats for blocked BUYs (planned X.9)"* |
| `PROJECT_BOOK.md` | §12 recommends X.9; §11 lists shadow validation as **not yet built** |
| `TAE_X8_LIVE_BOT_ADVISORY_INTEGRATION_SUMMARY.md` | X.8 = load advisory + `should_block_new_buy()` + **text logs only** |
| `TAE_INDIRECT_INTEGRATION_AUDIT_X7_FIX.md` | No TAE→LIVE write path except X.8 BUY gate; no shadow artifact chain |

---

## 3. X.9 requirement checklist (8 criteria)

| # | Requirement | Found? | Evidence |
|---|-------------|--------|----------|
| 1 | Log BUY allowed by `live_bot.py` | **Partial** | `bot_output.log` line `BUY executat: …` — unstructured, no advisory fields |
| 2 | Log BUY blocked by TAE `RISK_ADVISORY` | **Partial** | `bot_output.log` line `BUY blocat pentru {ticker}: TAE RISK_ADVISORY — …` — unstructured |
| 3 | Record block reason | **Partial** | Embedded in log string via `tae_block_reason`; not in CSV/JSON |
| 4 | Snapshot: ticker, signal, score, advisory action, confidence, block_new_buy, timestamp, price | **No** | Cycle-level summary in `advisory_runtime_summary()` only; per-ticker snapshot **not persisted** |
| 5 | Compare what would have happened for blocked BUYs | **No** | No forward PnL tracking for TAE-blocked candidates |
| 6 | Metrics: avoided losses, missed gains, neutral, profit/drawdown impact, gate accuracy | **No** | No aggregator for TAE gate |
| 7 | Report `tae_shadow_validation.json` / txt / md / csv | **No** | `Glob **/*shadow_validation*` → 0 files; `grep tae_shadow` → 0 matches |
| 8 | Connected to X.8 advisory gate or its log | **Partial** | X.8 **is** the gate; no downstream consumer of block events |

---

## 4. If EXISTS — canonical module

**N/A** — no module meets criteria 4–8.

---

## 5. EXISTS_PARTIAL — what was found and why it is insufficient

### 5.1 Closest to X.8 (partial — logging only)

| Module | Path | What it does | X.8 connection | Gap |
|--------|------|--------------|----------------|-----|
| Live advisory runtime | `research_core/governance/live_advisory_runtime.py` | Loads `tae_live_advisory.json`; `should_block_new_buy()` for `RISK_ADVISORY` | **Direct** — consumed by `live_bot.py` | No event store; no outcome analysis |
| Live bot integration | `live_bot.py` (`manage_portfolio`) | Logs cycle summary + per-ticker `BUY blocat … TAE RISK_ADVISORY` | **Direct** | Logs to `bot_output.log` only; not machine-readable; mixes non-TAE block reasons |

**Artifact produced:** `bot_output.log` (text), `tae_live_advisory.json` (cycle snapshot, not per-BUY)

### 5.2 Governance / advisory (partial — not shadow validation)

| Module | Path | What it does | Why not X.9 |
|--------|------|--------------|-------------|
| Live advisory bridge | `research_core/governance/live_advisory_bridge.py` | Builds `tae_live_advisory.json` from index + CSV + reports | Single aggregate advisory verdict; no per-BUY ledger |
| Advisory index | `research_core/governance/advisory_index.py` | Aggregates 85 `tae_*.json` reports | Report inventory, not live gate outcomes |

### 5.3 Paper tracking / validation (partial — wrong domain)

| Module | Path | Artifact | Why not X.9 |
|--------|------|----------|-------------|
| Paper tracking log | `research_core/strategy_evolution/paper_tracking_log.py` | `tae_paper_tracking_log.json` | Tracks **strategy candidates** toward promotion; not TAE `RISK_ADVISORY` blocks |
| Parallel paper validator | `research_core/strategy_evolution/parallel_paper_validator.py` | `tae_parallel_paper_validation.json` | Compares registry candidates vs baseline; not live bot BUY gate |
| Promotion gate | `research_core/strategy_evolution/promotion_gate.py` | `tae_strategy_promotion_gate.json` | Paper promotion decisions; unrelated to X.8 |

### 5.4 Counterfactual / attribution (partial — historical, not gate shadow)

| Module | Path | Artifact | Why not X.9 |
|--------|------|----------|-------------|
| Entry counterfactual | `research_core/entry_analysis/counterfactual_entry.py` | `tae_entry_counterfactual.json` | Replays **historical portfolio BUY rows** with alternate filters/sizing; does not read TAE gate events |
| Exit counterfactual | `research_core/exit_analysis/counterfactual_exit.py` | `tae_exit_counterfactual.json` | SELL counterfactuals only |
| Profit attribution | `research_core/profit_attribution/profit_attribution.py` | `tae_profit_attribution.json` | FIFO PnL attribution; no blocked-BUY cohort |
| Historical results analysis | `research_core/strategy_simulation/historical_results_analysis.py` | `tae_historical_results_analysis.json` | Backtest job outcomes; not live TAE gate |

### 5.5 Outcome / recommendation learning (partial — meta layer)

| Module | Path | Artifact | Why not X.9 |
|--------|------|----------|-------------|
| Recommendation outcome engine | `research_core/meta_intelligence/recommendation_outcome_engine.py` | `tae_recommendation_outcome.json`, registry | Validates **meta evolution recommendations** vs evidence; not live BUY blocks |
| Evidence accumulator | `research_core/evidence_history/evidence_accumulator.py` | `tae_evidence_history.json` | Candidate dossiers; "blocked" = evidence NOT_READY, not TAE gate |

### 5.6 Legacy shadow / missed-trade (partial — pre-TAE, orphan)

| Module | Path | Artifact | Why not X.9 |
|--------|------|----------|-------------|
| V41 shadow | `core/v41_shadow.py` | `v41_shadow_signals.csv` | Compares V4 vs V41 strategy on STRONG BUY; **not TAE**; used by orphan `research/signals.py` / v5_1 path |
| Threshold virtual tracker | `threshold_virtual_tracker.py` | `threshold_virtual_tracker.csv` | V14 threshold-80 virtual candidates; not connected to X.8 |
| Missed winners audit | `missed_winners_audit.py` | `missed_winners_audit_report.csv` | Score≥90 missed opportunities; no TAE fields |
| Signal → decision | `signal_to_decision_engine.py` | `decision_registry.csv` | Legacy paper registry; not read by `live_bot.py`; no TAE |

### 5.7 Demos searched

- **77+** `tae_phase*_demo.py` files — none named or described as shadow validation for live advisory gate
- `grep -i 'shadow_validation|tae_shadow|avoided_loss|missed_gain'` across `*.py` → **no matches** in active `research_core/` (only archive V41 shadow)

---

## 6. Proof of non-existence (X.9-specific)

```bash
# No shadow validation artifacts
Glob: **/*shadow_validation*     → 0 files
Glob: tae_shadow*                 → 0 files

# No code references
grep -r 'tae_shadow_validation'   → 0 matches (project root)
grep -r 'shadow_validation'       → 0 matches in research_core/

# SESSION_START / PROJECT_BOOK explicitly list X.9 as planned, not done
```

**X.8 produces only:**
- Unstructured log lines in `bot_output.log`
- Cycle-level `tae_live_advisory.json` (regenerated by demo; not an event ledger)

**No module:**
- Appends structured rows per blocked/allowed BUY
- Tags events with `advisory.action`, `confidence`, `block_new_buy`
- Runs forward price simulation on blocked cohort
- Emits `tae_shadow_validation.json`

---

## 7. What can be reused (do not rebuild)

| Reuse | Module | For X.9 |
|-------|--------|---------|
| ✅ | `live_advisory_runtime.py` | Load advisory state fields (action, confidence, blockers) |
| ✅ | `live_advisory_bridge.py` | Report persistence patterns (`to_dict`, JSON write) |
| ✅ | `advisory_index.py` | Index/report aggregation patterns |
| ✅ | `counterfactual_entry.py` | Scenario replay on BUY rows (adapt for forward outcomes) |
| ✅ | `missed_winners_audit.py` | Forward price change after signal (yfinance 2d) |
| ✅ | `recommendation_outcome_engine.py` | Outcome registry + evaluation cycle pattern |
| ✅ | X.8 log strings in `bot_output.log` | Optional retroactive parse (fragile; not canonical) |

| Do NOT rebuild / promote as X.9 | Reason |
|----------------------------------|--------|
| `paper_tracking_log.py` | Candidate promotion pipeline |
| `parallel_paper_validator.py` | Registry validation |
| `core/v41_shadow.py` | Legacy strategy A/B |
| `threshold_virtual_tracker.py` | V14 threshold experiment |
| `recommendation_outcome_engine.py` | Meta recommendations, not live gate |
| `entry_counterfactual.py` as-is | Historical filter scenarios, not TAE events |

---

## 8. Exact gap for X.9

1. **Structured event log** — one row per BUY decision (allowed / blocked-by-TAE / blocked-by-other) with required snapshot fields  
2. **Durable store** — CSV or JSONL append-only (not only `bot_output.log`)  
3. **Outcome evaluator** — forward mark-to-market for blocked BUY cohort over N days  
4. **Statistics layer** — avoided loss, missed gain, neutral, accuracy, profit/drawdown delta vs counterfactual “no gate”  
5. **Canonical reports** — `tae_shadow_validation.json` + human-readable summary  
6. **Explicit X.8 linkage** — events must record `source=tae_risk_gate` vs other block reasons  

---

## 9. Recommendation

### **`BUILD_NEW`** (primary)

X.9 requires a **new governance module** (e.g. under `research_core/governance/`) plus a **minimal structured hook** in `live_bot.py` (event append only — out of scope for this audit).

### **`EXTEND_EXISTING`** (secondary — reuse, not promote)

Extend patterns from:
- `live_advisory_runtime.py` (advisory fields)
- `live_advisory_bridge.py` / `advisory_index_report.py` (report store)
- `missed_winners_audit.py` / `counterfactual_entry.py` (forward outcome math)

Do **not** promote `core/v41_shadow.py`, `paper_tracking_log`, or `recommendation_outcome_engine` as canonical X.9.

### **Not recommended:** `PROMOTE_EXISTING_AS_CANONICAL`

No existing module satisfies requirements 4–8.

---

## 10. Summary table

| Layer | Status |
|-------|--------|
| X.8 risk gate (live) | ✅ Exists |
| Per-BUY structured logging | ❌ Missing |
| Blocked BUY outcome tracking | ❌ Missing |
| Shadow validation reports | ❌ Missing |
| Gate accuracy metrics | ❌ Missing |
| Canonical X.9 module | ❌ **Does not exist** |

---

## 11. Search scope executed

- `research_core/` (governance, strategy_evolution, evidence_*, meta_intelligence, entry/exit analysis, simulation)
- `research/`, `core/`
- All `tae_phase*_demo.py`
- Legacy: `decision_registry*`, `outcome_evaluator*`, `missed_winners*`, `threshold_*`, `v41_shadow`
- Artifacts: `tae_shadow*`, `*shadow_validation*`
- Keywords: shadow, RISK_ADVISORY, block_new_buy, avoided loss, missed gain, counterfactual, paper tracking, advisory, risk gate

---

*Audit only — no files modified except this report.*
