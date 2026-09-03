# TAE Existing Economic Proving Ground Audit

**Generated:** 2026-07-15  
**Mode:** READ ONLY  
**Scope:** Entire TAE ecosystem — code, runtime artifacts, CLI, dashboard, canonical docs  
**Companion:** `tae_existing_economic_proving_ground_audit.json`

**No code changes. No patches. No commits.**

---

## Verdict

```
ECONOMIC_PROVING_GROUND_EXISTS_FRAGMENTED
```

TAE does **not** contain a module, CLI, or document named “Economic Proving Ground.”

It **does** contain most lifecycle *pieces* under other names — ROI Queue artifacts, ROI-001 challenger replay, capital challengers, paper experiments, adaptive weights, rule survival, DPE dual-arm, profit-optimization audits, decision-replay promotion, watchlist promotion queue — but they are **parallel, not closed**.

There is **no single automatic loop**:

ROI #1 → durable challenger registry → every full-paper-cycle evidence → economic gates → promote/reject/rollback → queue advance → dashboard.

---

## Desired lifecycle vs current status

| Stage | Status | Where it lives today |
|-------|--------|----------------------|
| ROI opportunity | **partial / manual** | `tae_roi_queue.json`, `tae_next_dollar.json`, Economic ROI master report |
| Challenger registration | **fragmented** | Capital challengers auto; ROI-001 report+flag; profit-opt ephemeral; no unified registry |
| Baseline vs challenger | **partial** | Multiple independent replays (ROI-001, profit-opt, conversion, DPE, replay-promo) |
| Auto evidence each PAPER cycle | **partial** | Experiments / weights / rules / DPE / capital observe **yes**; ROI-001 / ROI queue / profit-opt **no** |
| Economic metrics suite | **partial** | Best in ROI-001 + DPE + profit-opt; capital challengers thinner |
| Promote / reject / retire | **partial** | Hints + report verdicts; **no** production flip for ROI; live lock always false |
| Rollback failed challenger | **missing / narrative** | ROI-001 never left baseline; profit-opt `NotImplementedError` |
| Only one active ROI | **manual policy** | Written in queue docs; not enforced in code |
| Queue advance after completion | **manual** | “Recalculate queue” instruction; no regenerator |
| Dashboard / CLI visibility | **missing for this lifecycle** | Dashboard has **watchlist** promotion queue only |

---

## Component answers (checklist)

For each component: (1) permanent register (2) preserve baseline (3) auto-update every full-paper-cycle (4) track sample / Δrealized / Δunrealized / Δexpectancy / ΔPF / ΔDD / Δcap-eff (5) min sample (6) auto promote (7) auto reject/retire (8) rollback (9) only one active ROI (10) queue auto-advance (11) CLI/dashboard (12) SSOT status (13) auto vs manual

### 1. ROI Queue + Next Dollar

| Q | Answer |
|---|--------|
| Files | `TAE_ROI_QUEUE.md`, `tae_roi_queue.json`, `TAE_NEXT_DOLLAR.md`, `tae_next_dollar.json` |
| Functions | **None** — no Python builder/regenerator |
| 1 Permanent register | Policy only |
| 2 Preserve baseline | N/A |
| 3 Auto cycle evidence | **No** |
| 4 Metric deltas | Score formula stored; not live-fed from cycles |
| 5 Min sample | Documented in formula (`sample_f`) |
| 6–8 Promote/reject/rollback | Policy text only |
| 9 One active ROI | Policy yes (`work_rule`); **unenforced** |
| 10 Queue advance | **No** |
| 11 Visible | **No** CLI · **No** dashboard |
| 12 SSOT | Hand-authored JSON |
| 13 Mode | **Manual** |

### 2. ROI-001 Challenger (PTA trim)

| Q | Answer |
|---|--------|
| Files | `tae_roi001_challenger.py`, hooks in `tae_paper_execution.py`, `tae_roi001_challenger_report.json` |
| Functions | `run_roi001_challenger`, `collect_reduce_opportunities`, `resolve_reduce_trim_pct`, `baseline_reduce_trim_pct`, `execute_decision(..., roi001_challenger=False)` |
| 1 Permanent register | Partial — report + dormant flag; **not** in `capital_challengers.json` |
| 2 Preserve baseline | **Yes** — production default `roi001_challenger=False`; cycle never enables it |
| 3 Auto cycle evidence | **No** — not in `CYCLE_STEPS` / structural governance |
| 4 Metrics | **Yes** — sample, realized, remain UPNL, expectancy, PF, DD, cap-eff, cash |
| 5 Min sample | **Yes** — `MIN_REDUCE_EXECUTIONS=10`, `MIN_TICKERS=3` |
| 6 Auto promote | **No** — report can say `ROI001_PROMOTED`; does not flip production |
| 7 Auto reject/retire | Report verdict only; does not update ROI queue |
| 8 Rollback | Narrative `baseline_restored`; production never left baseline |
| 9–10 One ROI / advance | Out of scope / **no** |
| 11 Visible | Manual `python3 tae_roi001_challenger.py` only |
| 12 SSOT | `tae_roi001_challenger_report.json` |
| 13 Mode | **One-shot replay** (re-runnable, not cycle-gated) |

### 3. Paper experiments

| Q | Answer |
|---|--------|
| Files | `tae_paper_experiment_runner.py`, CLI `tae.py paper-experiments` |
| Functions | `run_experiments`, `score_hypothesis`, `assign_verdict` |
| SSOT | `runtime_outputs/learning_to_profit/experiment_results.json` |
| 1 Register | Queue / results files |
| 2 Baseline | Simulated vs baseline metrics (not config freeze) |
| 3 Auto cycle | **Yes** — `CYCLE_STEPS` + structural cycle |
| 4 Metrics | Expected profit/risk deltas; not full ROI economic dashboard |
| 5 Min sample | Soft (`NEEDS_MORE_DATA`) |
| 6–8 | Verdicts PROMISING/REJECT; **no** live promote; no ROI rollback |
| 9–10 | No ROI linkage |
| 11 | CLI yes · dashboard no |
| 13 | **Automatic** each paper cycle |

### 4. Validation → Capital Challengers

| Q | Answer |
|---|--------|
| Files | `tae_paper_decision_engine.py`, `tae_structural_governance.py`, `capital_challengers.json` |
| Functions | `classify_experiment_capital_eligibility`, `apply_experiment_capital_evidence`, `update_capital_challenger_registry` |
| 1 Permanent register | **Yes** — `runtime_outputs/learning_to_profit/capital_challengers.json` |
| 2 Preserve baseline | PDE authority; Hard Risk non-bypassable; bounded REDUCE |
| 3 Auto cycle | **Yes** — `capital_challenger_observe` after execution |
| 4 Metrics | Observed fill/realized; **not** full PF/expectancy/DD suite |
| 5 Min sample | Eligibility floors on lifecycle sample / profit_delta |
| 6 Auto promote | **Hints only** (`PROMOTED_CANDIDATE`); comment: “Promotion/retirement deferred” |
| 7 Auto reject | Hint `REVERT_OR_RETIRE`; does **not** disable experiment |
| 8 Rollback | Documented condition; **no** auto config restore |
| 9–10 | Not tied to ROI queue |
| 11 | Via cycle · no dedicated dashboard board |
| 13 | Observe **auto**; promote/retire **manual** |

### 5. Adaptive weights + constitutional evolution

| Q | Answer |
|---|--------|
| Files | `tae_adaptive_paper_weights.py`, `tae_full_paper_cycle.compare_constitutional_evolution` |
| 3 Auto cycle | **Yes** |
| 4 | Weight multipliers from verdicts — not ROI challenger economics |
| 6 | PAPER weights only; `live_promotion_allowed=false` |
| 13 | **Automatic** |

### 6. Rule survival / longitudinal / outcome memory

| Q | Answer |
|---|--------|
| Files | `tae_rule_survival.py` (`classify_rule_state`, `build_rule_lifecycle`), `tae_longitudinal_outcome_memory.py` |
| 3 Auto cycle | **Yes** |
| 5 Min sample | `MIN_EVIDENCE=5`, `MIN_TRUSTED=10` |
| 6–7 | States TRUSTED/DISABLED auto; influence multipliers |
| 13 | **Automatic** |

### 7. Profit optimization (baseline vs challengers)

| Q | Answer |
|---|--------|
| Files | `tae_profit_optimization.py`, CLI `tae.py profit-optimization` |
| Functions | `define_challengers`, `replay_challengers`, `select_calibration`, `apply_promoted_calibration` |
| 3 Auto cycle | **No** |
| 6 Auto promote | Path raises `NotImplementedError` |
| 13 | **Manual one-shot audit** |

### 8. Decision replay / protection promotion

| Q | Answer |
|---|--------|
| Files | `tae_decision_replay_composer.py`, `tae_decision_replay_promotion.py` |
| Functions | `evaluate_promotion`, `run_promotion_audit` |
| Current | `REPLAY_VALUE_NOT_REPRODUCIBLE` |
| 3 Auto cycle | **No** |
| 13 | **Manual / one-shot** |

### 9. DPE competitive / collaborative / adaptive

| Q | Answer |
|---|--------|
| Files | `tae_dpe_*`, CLI `dpe-*`, `runtime_outputs/dpe/**` |
| 3 Auto cycle | **Yes** (`CYCLE_STEPS`) |
| 4 | Arm PnL / PF / DD via evaluator |
| 6 | **No live promote**; adaptive advisory only |
| 9 | Separate proving ground from ROI queue |
| 13 | Cycle **auto**; selection **advisory** |

### 10. Conversion / blocker / attrition challengers

| Q | Answer |
|---|--------|
| Files | `tae_conversion_breakthrough.py`, opportunity-attrition path |
| 3 Auto cycle | **No** |
| 13 | **Report-only / one-shot** |

### 11. Dashboard

| Q | Answer |
|---|--------|
| File | `dashboard_tae_command_center.py` |
| Shows | Watchlist `tae_promotion_queue.json` (`render_promotion_queue_panel`) |
| ROI / capital challengers / ROI-001 / paper experiments | **Missing** |

### 12. Live promotion lock

| Q | Answer |
|---|--------|
| Files | `tae_live_promotion_lock.py`, `build_promotion_gate` in `tae_full_paper_cycle.py` |
| Role | Hard stop on live — **not** an ROI economic challenger lifecycle |

### Canonical docs

| Doc | Finding |
|-----|---------|
| `PROJECT_BOOK.md` | References capital-allocation audit, profit-optimization CLI, attrition, decision-replay promotion — **no** Economic Proving Ground |
| `SESSION_START.md` | Documents capital challenger closure + attrition rejections — **no** ROI queue automation |
| `TAE_DEVELOPMENT_PROTOCOL.md` | Strategy promotion gates; **no auto-promote to live**; human review required |

---

## Lifecycle map (exact files / functions)

```
ROI opportunity
  └─ manual artifacts: tae_roi_queue.json / tae_next_dollar.json
     (no build_roi_queue())

→ Challenger registration
  ├─ CAPITAL path (auto): classify_* / apply_experiment_capital_evidence
  │     → capital_challengers.json via update_capital_challenger_registry()
  ├─ ROI-001 path (dormant): resolve_reduce_trim_pct + roi001_challenger=False
  │     → state in tae_roi001_challenger_report.json only
  └─ OTHER: profit-opt / conversion / DPE arms (parallel, not ROI-gated)

→ PAPER cycles (automatic subset)
  └─ CYCLE_STEPS: paper-decisions → paper-execution → paper-experiments
       → outcome-memory → adaptive-weights → dpe-* → strategy-survival
     + structural: capital_challenger_observe
     − NOT CALLED: run_roi001_challenger(), ROI queue rebuild, profit-optimization

→ Evidence
  ├─ capital_challengers.json (observed_realized_pnl, promotion_hint)
  ├─ experiment_results.json / adaptive weights / rule_lifecycle
  ├─ DPE evaluation JSON
  └─ ROI-001 metrics ONLY when operator re-runs tae_roi001_challenger.py

→ Verdict
  ├─ capital: PROMOTED_CANDIDATE / REVERT_OR_RETIRE (hint)
  ├─ ROI-001: ROI001_* report verdict (no production switch)
  └─ profit-opt / replay-promo: report-only / rejected

→ Promotion / Retirement
  ├─ live: blocked (live_promotion_allowed=false)
  ├─ PAPER production config flip for ROI-001: MISSING
  └─ rollback: MISSING (or no-op because baseline never left)

→ Queue advancement
  └─ MISSING (manual “recalculate tae_roi_queue.json”)

→ Visibility
  └─ dashboard: watchlist promotion only — ROI proving ground MISSING
```

---

## ROI-001 explicit inspection

| Question | Answer |
|----------|--------|
| Where is challenger state stored? | `tae_roi001_challenger_report.json` (+ MD twin). Code path gated by `execute_decision(..., roi001_challenger=False)`. **Not** in `capital_challengers.json`. |
| Do future REDUCE cases accumulate automatically? | **No.** `collect_reduce_opportunities()` re-reads all `EXECUTED` `REDUCE_PAPER` from `paper_orders.jsonl` **only when** `run_roi001_challenger()` is run. Not hooked into `full-paper-cycle`. |
| Will n=4 become n=5, n=6 automatically? | Order history **can** grow under **baseline** REDUCE. Evidence counter / report **does not** refresh unless manually re-run. |
| Auto-promote at n≥10 if gates pass? | **No.** Report may emit `ROI001_PROMOTED` + `commit: true`, but production stays `roi001_challenger=False`. No CLI/cycle step flips the flag. |
| Failure → auto reject/rollback? | Report can say `ROI001_REJECTED` / `baseline_restored`. Production never left baseline → rollback is no-op. Does **not** retire ROI-001 in the queue. |
| Does ROI-002 auto-activate afterward? | **No.** Queue JSON has `"depends_on": "ROI-001"` as data only. No Python advances `#1`. |

Current report verdict: **`ROI001_NEEDS_MORE_EVIDENCE`** (n=4 &lt; 10).

---

## What is automatic vs manual

### Automatic (inside `python3 tae.py full-paper-cycle`)

- Paper decisions + execution  
- Paper experiments  
- Outcome / longitudinal memory  
- Adaptive weights (+ post-learning constitutional evolution)  
- DPE event → split → competitive/collaborative → eval → learning → adaptive  
- Strategy / rule survival  
- Capital challenger observe (`update_capital_challenger_registry`)

### Manual / operator / Codex

- Authoring / recalculating ROI Queue & Next Dollar  
- Running `python3 tae_roi001_challenger.py`  
- Enabling `roi001_challenger=True` (never done in production)  
- `tae.py profit-optimization`, conversion / attrition challenger audits  
- Decision-replay promotion audit  
- Advancing from ROI-001 → ROI-002  
- Any dashboard view of this lifecycle  

---

## Duplicate-risk assessment

**HIGH.** Multiple “challenger / prove / promote” surfaces compete on the same PAPER history:

| Surface | Overlap |
|---------|---------|
| ROI-001 PTA REDUCE size | Execution sizing on REDUCE |
| Capital challengers (PROMISING→REDUCE) | Same REDUCE path / same tickers (HSBA, AAPL, PG, GE) |
| Profit-optimization calibrations | Another baseline-vs-challenger suite |
| Conversion / attrition blockers | Another one-shot promote path |
| DPE competitive vs collaborative | Parallel philosophy proving ground |
| Decision-replay protection promotion | Shadow protect/cooldown prove |
| Dashboard watchlist promotion queue | Different domain; easy name confusion |

Without one SSOT for “active economic ROI challenger,” “PROMOTED” can mean candidate **hint**, report **verdict**, or watchlist **approve** — not the same thing.

---

## Smallest reuse-only closure path (if closing the gap)

Describe only — **do not build now**:

1. After `paper-execution`, call existing `run_roi001_challenger()` from the same structural point as `update_capital_challenger_registry` so n accumulates every cycle from `paper_orders.jsonl`.
2. Treat `tae_roi001_challenger_report.json` as status SSOT (optionally mirror one row into `capital_challengers.json` for a single pane — no new schema if avoidable).
3. On `ROI001_PROMOTED` only: persist a config consumed by `execute_decision` (keep default False until then). Reuse `resolve_reduce_trim_pct` / baseline helpers.
4. On reject: leave flag False; mark ROI-001 readiness in existing `tae_roi_queue.json`.
5. After promote/reject: regenerate Next Dollar from the existing queue JSON score fields (script mirroring formula already in the artifact) — enforce one active `#1`.
6. Dashboard: reuse `render_promotion_queue_panel` pattern to **read** ROI queue + ROI-001 report + capital challengers — no new engine.

Defer merging DPE / profit-opt into this loop (duplicate consolidation later).

---

## Final verdict

```
ECONOMIC_PROVING_GROUND_EXISTS_FRAGMENTED
```
