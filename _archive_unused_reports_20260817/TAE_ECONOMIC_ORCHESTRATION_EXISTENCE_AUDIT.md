# TAE Economic Orchestration Existence Audit

**Generated:** 2026-07-15  
**Mode:** READ ONLY  
**Companion:** `tae_economic_orchestration_existence_audit.json`

No code changes. No commits. No new orchestrator.

---

## Verdict

```
ECONOMIC_ORCHESTRATION_PARTIALLY_EXISTS
```

TAE **does** orchestrate a large PAPER cycle automatically (`tae.py full-paper-cycle` → `run_structural_paper_cycle`). That cycle includes experiments, weights, DPE, rule survival, and **capital challenger observe**.

TAE **does not** orchestrate the **ROI economic lifecycle** end-to-end. ROI Queue / Next Dollar are static artifacts. ROI-001 challenger code exists but is **not called** inside the cycle, **does not** flip production config, and **does not** advance the queue. Dashboard has no ROI/challenger board.

There is no module named “Economic Orchestrator.” The closest active orchestrator is `tae_structural_governance.run_structural_paper_cycle` — a **different** (broader) loop.

---

## Required lifecycle — step-by-step

| Step | Exists | File / function | Automatic | Persistent state | Gap |
|------|:------:|-----------------|:---------:|------------------|-----|
| **1. Active ROI identified** | Partial | `tae_roi_queue.json`, `tae_next_dollar.json` | **Manual** | JSON artifacts (hand-authored) | No runtime reader/enforcer; no code sets `#1` |
| **2. Challenger runs in full-paper-cycle** | Partial | Capital: `update_capital_challenger_registry()` in `tae_structural_governance.py` L716–729 | **Yes** (capital path) | `capital_challengers.json` | **ROI-001:** `run_roi001_challenger()` **not** in cycle |
| **3. Sample size increases automatically** | Partial | Capital observe updates registry each cycle | **Yes** (capital) | `capital_challengers.json` | **ROI-001:** n only updates if operator re-runs script |
| **4. Economic metrics update automatically** | Partial | ROI-001: `run_roi001_challenger()`; DPE: cycle steps | **Mixed** | `tae_roi001_challenger_report.json`, `runtime_outputs/dpe/**` | ROI report stale between manual runs |
| **5. Promotion/rejection gate runs automatically** | Partial | ROI-001 gates in `run_roi001_challenger()`; live gate in `build_promotion_gate` | **No** (ROI) / **Yes** (live lock always false) | Report JSON | Gates run only on manual ROI script |
| **6. Production flag/config changes automatically** | **No** | `execute_decision(..., roi001_challenger=False)` default; `run_paper_execution` never passes `True` | **No** | No persistent ROI config file | Promotion cannot affect live execution |
| **7. Failed challenger rolls back automatically** | **No** | Report field `baseline_restored` in `tae_roi001_challenger.py` | **No** | N/A | Baseline never left; no mutative rollback |
| **8. ROI Queue advances automatically** | **No** | Policy in `TAE_ROI_QUEUE.md` only | **No** | `tae_roi_queue.json` static | No regenerator / advancer |
| **9. Next ROI becomes active automatically** | **No** | `depends_on: ROI-001` in queue JSON (data only) | **No** | — | ROI-002 never auto-activates |
| **10. Dashboard/CLI shows current state** | Partial | CLI: many audit commands; dashboard: `render_promotion_queue_panel` (watchlist) | **Manual** | `tae_promotion_queue.json` | **No** ROI / ROI-001 / capital-challenger board |

---

## Per-step detail (10 questions each)

### Step 1 — Active ROI

| Q | Answer |
|---|--------|
| File/function | `tae_roi_queue.json`, `tae_next_dollar.json` — **no Python** |
| Automatic | **Manual** artifact authorship |
| In full-paper-cycle | **No** |
| Persistent state | JSON files in repo root |
| Idempotent | N/A (not executed) |
| Auto promote/reject/rollback/advance/ROI-002 | **No** |

### Step 2 — Challenger in cycle

| Q | Answer |
|---|--------|
| File/function | `tae_structural_governance.run_structural_paper_cycle` → `update_capital_challenger_registry()` (`tae_paper_decision_engine.py` L2669+) |
| Automatic | **Yes** for capital challengers after `paper-execution` |
| In full-paper-cycle | **Yes** |
| Persistent state | `runtime_outputs/learning_to_profit/capital_challengers.json` |
| Idempotent | **Yes** — merges prior registry, re-observes orders |
| Auto promote | **No** — hints only (`promotion_hint`; comment L2732: “deferred”) |
| Auto reject/retire | **No** — hint `REVERT_OR_RETIRE` only |
| Rollback | **No** |
| Queue advance / ROI-002 | **No** |

**ROI-001:** `run_roi001_challenger()` in `tae_roi001_challenger.py` — **separate script only**, not imported by cycle.

### Step 3–4 — Sample + metrics (ROI-001)

| Q | Answer |
|---|--------|
| File/function | `collect_reduce_opportunities()` reads full `paper_orders.jsonl`; `run_roi001_challenger()` recomputes all metrics |
| Automatic | **No** — requires `python3 tae_roi001_challenger.py` |
| In full-paper-cycle | **No** |
| Persistent state | `tae_roi001_challenger_report.json` (overwritten each run) |
| Idempotent | **Yes** on re-run — full rebuild from order history |
| Cumulative | **Rebuilt from history** each run (not incremental append), but n grows when new baseline REDUCE orders exist |

### Step 5 — Promotion gate (ROI-001)

| Q | Answer |
|---|--------|
| File/function | `run_roi001_challenger()` promotion_checks L227–239; verdict L254–261 |
| Automatic | **No** |
| Can promote at n≥10 | **Report only** — can emit `ROI001_PROMOTED`; does not change production |
| Auto reject | Report `ROI001_REJECTED` only |

### Step 6 — Production config flip

| Q | Answer |
|---|--------|
| File/function | `resolve_reduce_trim_pct`, `execute_decision(roi001_challenger=False)` in `tae_paper_execution.py` |
| `run_paper_execution` L2040–2046 | Calls `execute_decision` **without** `roi001_challenger` → always **False** |
| Persistent config | **None** — no JSON/env flag file for ROI-001 enablement |
| Consumed by normal execution | **Only if** caller passes `roi001_challenger=True` (never in production path) |

### Steps 7–10 — Rollback, queue, ROI-002, visibility

All **missing or manual** for the ROI lifecycle. Dashboard grep: **zero** matches for `roi`, `ROI`, `next_dollar`, `capital_challenger`, `roi001`.

---

## ROI-001 explicit verification

| Question | Answer |
|----------|--------|
| Is `run_roi001_challenger()` called automatically? | **No.** Not in `CYCLE_STEPS` (`tae_full_paper_cycle.py` L58–76), not in `run_structural_paper_cycle` steps after execution. |
| Does n=4 → n=5 after next eligible REDUCE without manual CLI? | **No.** New baseline REDUCEs append to `paper_orders.jsonl`, but report **stays at n=4** until script re-run. |
| Cumulative or rebuilt? | **Rebuilt from full order history** on each script invocation (not incremental state machine). |
| At n≥10, can status become `ROI001_PROMOTED` automatically? | **No.** Only when operator runs script; even then does not enable production. |
| Does promotion flip `roi001_challenger=True`? | **No.** Report may set `commit: true`; no code writes persistent enablement. |
| Is flag consumed by normal execution? | **Yes, if set** — but production path never sets it. |
| If results worsen, baseline restored automatically? | **No.** Production always baseline; report may say `baseline_restored`. |
| ROI-002 activated automatically after ROI-001? | **No.** `tae_roi_queue.json` rank 2 has `"depends_on": "ROI-001"` as metadata only. |

Current report: **`ROI001_NEEDS_MORE_EVIDENCE`**, n=4, tickers AAPL/GE/HSBA.L/PG.

---

## Lifecycle map

```
ACTIVE ROI (#1)
  tae_roi_queue.json / tae_next_dollar.json
  Status: MANUAL ARTIFACTS — not read by cycle

→ CHALLENGER IN CYCLE
  ├─ Capital path: AUTO
  │    tae_structural_governance.run_structural_paper_cycle
  │    → update_capital_challenger_registry()
  │    → capital_challengers.json
  └─ ROI-001 path: DORMANT
       tae_roi001_challenger.run_roi001_challenger (manual script)
       execute_decision(roi001_challenger=False) in run_paper_execution

→ FULL-PAPER-CYCLE (tae.py full-paper-cycle)
  Delegates: tae_full_paper_cycle.main → run_structural_paper_cycle
  Auto: health, decisions, execution, MTM, experiments, weights, DPE×6, survival, canonical-vs-paper
  Auto: capital_challenger_observe
  NOT called: run_roi001_challenger, ROI queue rebuild, profit-optimization

→ EVIDENCE
  Auto: experiment_results, adaptive weights, rule_lifecycle, DPE eval, capital_challengers
  Manual/stale: tae_roi001_challenger_report.json

→ VERDICT / GATES
  Auto: live promotion lock (always false)
  Manual: ROI-001 promotion_checks in report
  Hints only: capital promotion_hint (no config change)

→ PRODUCTION CONFIG
  MISSING for ROI-001 (flag never flipped)

→ ROLLBACK
  MISSING (baseline never left)

→ QUEUE ADVANCE / ROI-002
  MISSING

→ DASHBOARD / CLI
  Watchlist promotion queue only (tae_promotion_queue.json)
  ROI proving ground: MISSING
```

---

## Automatic vs manual

### Automatic (inside `full-paper-cycle`)

- `run_structural_paper_cycle` — full ranked governance pipeline  
- `paper-decisions` → `paper-execution` → `capital_challenger_observe`  
- `paper-experiments`, `outcome-memory`, `adaptive-weights`  
- DPE stack (events → splitter → competitive/collaborative → evaluator → learning → adaptive)  
- `strategy-survival`, constitutional evolution (post-learning)  
- `build_promotion_gate` + `enforce_promotion_gate` (live always blocked)

### Manual / operator / Codex

- Authoring `tae_roi_queue.json` / `tae_next_dollar.json`  
- `python3 tae_roi001_challenger.py`  
- Enabling `roi001_challenger=True` (never done)  
- Advancing ROI-001 → ROI-002  
- Economic ROI dashboard (does not exist)  
- `tae.py profit-optimization`, conversion/attrition audits (separate one-shots)

---

## Git history (orchestration-related)

Recent commits show **PAPER cycle orchestration** and **capital allocation closure**, not ROI economic orchestration:

- `7e7ee30` — validation-to-capital-allocation loop  
- `7c4f6a0` / `c5ce77c` — constitutional evolution in full-paper-cycle  
- `7ad4633` — operational consistency and refresh orchestration  
- `d5ae01b` — full PAPER cycle from existing intelligence  

No commit found wiring `run_roi001_challenger` into `run_structural_paper_cycle`.

---

## Duplicate-risk assessment

**HIGH.** Parallel orchestration surfaces without one SSOT for “active economic ROI challenger”:

| Surface | Active in cycle? |
|---------|------------------|
| Capital challengers (`capital_challengers.json`) | **Yes** |
| ROI-001 replay report | **No** |
| ROI Queue / Next Dollar | **No** |
| DPE dual-arm | **Yes** |
| Profit-optimization audit | **No** |
| Dashboard watchlist promotion | **Separate domain** |

Same REDUCE tickers (HSBA, AAPL, PG, GE) can appear in capital challengers and ROI-001 replay with different “promotion” semantics.

---

## Smallest reuse-only closure path (if completing — describe only)

1. After `paper-execution`, call existing `run_roi001_challenger()` beside `update_capital_challenger_registry()` (same file, ~L730).  
2. Use `tae_roi001_challenger_report.json` as ROI status SSOT; optional mirror into `capital_challengers.json`.  
3. On `ROI001_PROMOTED` only: persist enable flag read by `run_paper_execution` → `execute_decision(roi001_challenger=...)`.  
4. On reject: keep flag false; update readiness in `tae_roi_queue.json`.  
5. Script to regenerate Next Dollar from existing queue score formula after verdict.  
6. Dashboard: extend `dashboard_tae_command_center.py` read-only panel (pattern: `render_promotion_queue_panel`).

No new orchestrator module required — extend `run_structural_paper_cycle` only.

---

## Canonical docs

| Doc | ROI orchestration? |
|-----|-------------------|
| `PROJECT_BOOK.md` | Capital allocation audit referenced; no ROI queue automation |
| `SESSION_START.md` | Capital challenger closure documented; no ROI-001 cycle wiring |
| `TAE_DEVELOPMENT_PROTOCOL.md` | Live promotion requires human review; no auto ROI promote |

---

## Final verdict

```
ECONOMIC_ORCHESTRATION_PARTIALLY_EXISTS
```
