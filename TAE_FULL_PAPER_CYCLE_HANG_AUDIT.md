# TAE Full Paper Cycle Hang Audit

**Generated:** 2026-07-15  
**Verdict:** `FULL_PAPER_CYCLE_HANG_CLOSED`  
**Trigger commit:** `7c4f6a0` (constitutional evolution loop)  
**Fix scope:** orchestration visibility + bounded subprocess timeouts — no strategy/scoring changes

---

## Symptom

After commit `7c4f6a0`, `python3 tae.py full-paper-cycle` appeared to hang indefinitely. Visible output stopped at:

```text
===== TAE STRUCTURAL GOVERNANCE — FULL PAPER CYCLE =====
Mode: PAPER_ONLY | NO_BROKER | NO_LIVE_PROMOTION
```

Operator Ctrl+C traceback showed the CLI parent blocked on `subprocess.run()` waiting for `tae_full_paper_cycle.py`.

---

## Diagnosis

### Blocked function / child command

| Layer | Function | Child |
|-------|----------|-------|
| CLI | `tae_cli/commands/full_paper_cycle.py` | `python3 tae_full_paper_cycle.py` |
| Cycle | `run_structural_paper_cycle()` rank-1 gate | `gate_data_validity(root)` |
| **Exact hang** | **`gate_data_validity()`** | **`run_historical_runtime_refresh()` → `_run_script()` refresh subprocesses** |

Isolated profiling:

```text
[START] gate_data_validity 18:13:59
[END] gate_data_validity 18:16:08 duration=130.4s status=PASS
```

No `[START]`/`[END]` existed before the fix; the operator saw zero progress for ~130s.

### Ruled out

| Hypothesis | Result |
|------------|--------|
| Recursive `full-paper-cycle` | **No** — grep found no re-entry from pre_pde_feedback, PDE, or post-learning evolution |
| File lock / live_bot artifact conflict | **No** |
| Malformed JSONL scan hang | **No** — not on critical path before first CLI step |
| post-learning PDE recursion | **No** — PDE `main()` inline only |

### Root cause

**Silent historical runtime refresh on cycle rank-1 gate.**

`run_structural_paper_cycle()` prints the header, then immediately calls `gate_data_validity()` → `run_historical_runtime_refresh()`. That function audits 8 historical/strategic sources and sequentially runs refresh scripts (yfinance/network) for any STALE/MISSING source. Subprocesses used `capture_output=True` with no step tracing, so multi-minute network refreshes produced **zero visible output** between the header and the first `>>> [accounting_snapshot]` line.

This is environment/timing dependent: when sources are FRESH the step completes in ~1–2s; when stale it can exceed 2 minutes per source (300s timeout each).

---

## Fix (minimal)

1. **Step tracing** — `[START]` / `[END]` / `[FAIL]` / `[TIMEOUT]` on:
   - `run_historical_runtime_refresh()` (audit, per-source, recompute, scripts)
   - `gate_data_validity`, `run_cli_step`, `structural_paper_cycle`
   - `run_pre_pde_feedback`, `run_post_learning_evolution`
2. **Unbuffered output** — `python -u` + `PYTHONUNBUFFERED=1` on orchestration subprocesses; CLI wrapper uses `-u`.
3. **Bounded CLI timeouts** — `run_cli_step()` default 600s with `[TIMEOUT]` verdict and exit 124 (child killed cleanly).
4. **Preserved** — constitutional evolution loop (`7c4f6a0`), Profit Integrity, Hard Risk, Decision State, reconciliation, $30,000 capital base.

No new engine. No new module. Evolution loop not disabled.

---

## Duration before / after

| Metric | Before fix | After fix |
|--------|------------|-----------|
| Visible output after header | 0s (appears hung) | Immediate `[START] gate_data_validity` |
| `gate_data_validity` (fresh sources) | ~130s silent (stale refresh case) | **1.7s** with per-source trace |
| Full cycle (`python3 -u tae_full_paper_cycle.py`) | interrupted | **42s** |
| CLI cycle 1 | interrupted | **43.6s** |
| CLI cycle 2 (consecutive) | — | **44.6s** |

---

## Validation

### Commands (all completed without manual interruption)

```bash
python3 -u tae_full_paper_cycle.py          # exit 0
python3 tae.py full-paper-cycle             # exit 0 (×2 consecutive)
python3 tae.py morning-audit                # RECONCILIATION PASS, capital $30,000
python3 tae.py profit-pipeline              # integrity CLOSED, reconciliation PASS
```

### Constitutional evolution

- `loop_closed`: **true**
- Decision deltas: **11**
- Weight deltas: **1**
- Artifact: `runtime_outputs/governance/constitutional_evolution.json`

### Integrity

| Check | Result |
|-------|--------|
| Profit Integrity | `PAPER_PROFIT_INTEGRITY_CLOSED` |
| Reconciliation | **PASS** |
| Capital base | **$30,000 CONFIRMED** |
| Orphan cycle processes | none |
| Duplicate orders/trades/DPE | none observed (116 orders / 28 trades stable) |

### Tests

```bash
python3 -m unittest \
  tae_full_paper_cycle_test \
  tae_paper_execution_test \
  tae_paper_decision_engine_test \
  tae_decision_state_test \
  tae_profit_pipeline_test -v
```

**86 tests OK**

---

## Files changed

- `tae_historical_runtime_refresh.py` — trace helpers, per-source/script tracing, `-u` on refresh subprocesses
- `tae_structural_governance.py` — `run_cli_step` timeout + unbuffered + tracing; cycle-level trace
- `tae_full_paper_cycle.py` — pre/post evolution tracing
- `tae_cli/commands/full_paper_cycle.py` — `python3 -u` wrapper

Machine-readable evidence: `tae_full_paper_cycle_hang_audit.json`
