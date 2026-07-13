# TAE Profit Pipeline Consolidation Audit

**Generated:** 2026-07-13  
**Verdict:** `PROFIT_PIPELINE_CONSOLIDATED`  
**Prior audit:** `PROFIT_PIPELINE_EXISTS_FRAGMENTED`  
**Machine-readable:** `tae_profit_pipeline_consolidation_audit.json`

---

## Summary

Built a **read-only consolidation layer** (`tae_profit_pipeline.py`) that joins existing artifacts on `decision_id` / `ticker` without changing PDE, execution, risk, or portfolio behavior.

No new trading engine. No execution mutations. Outputs:

- `TAE_PROFIT_PIPELINE_REPORT.md`
- `tae_profit_pipeline.json`

Integrated into:

- `python3 tae.py morning-audit` (summary section)
- `python3 tae.py profit-pipeline` (standalone)
- `dashboard_v2.py` Performance tab — **Profit Pipeline** section

---

## Implementation

| Component | Role |
|-----------|------|
| `tae_profit_pipeline.py` | `build_profit_pipeline()` — join + metrics + reports |
| `tae_morning_operational_audit.py` | Calls builder read-only; embeds summary |
| `tae_cli/commands/profit_pipeline.py` | CLI entry |
| `dashboard_v2.py` | Read-only dashboard section |
| `tae_profit_pipeline_test.py` | 5 unit tests |

**Join priority:** `decision_id` → ticker+cycle → ticker with `LOW_CONFIDENCE_JOIN` / `INFERRED_NO_ORDER`

**Cycle scoping:** Orders/trades filtered to `paper_decisions.json` `generated_at` so conversion metrics reflect the current PDE cycle honestly.

---

## Validation evidence

```bash
python3 tae.py full-paper-cycle          # PASS
python3 tae.py morning-audit             # integrity PASS, reconciliation PASS, pipeline section present
python3 tae.py morning-audit             # orders/trades jsonl mtime unchanged
python3 tae.py profit-pipeline           # PASS
python3 -m unittest tae_profit_pipeline_test tae_paper_execution_test tae_full_paper_cycle_test -v  # 41 OK
```

| Check | Result |
|-------|--------|
| Repeated morning-audit mutates portfolio/ledgers | **No** (orders/trades mtime unchanged) |
| Duplicate pipeline rows | **0** (one row per decision_id) |
| PnL matches PAPER portfolio SSOT | **Yes** (-451.60 / -74.62 / -185.30 vs base) |
| Block reasons from paper_orders + inference | **Yes** |
| decision_id join coverage reported | **Yes** (honest 0/25 when cycle has no new orders) |
| Profit Integrity | **PASS** (`PAPER_PROFIT_INTEGRITY_CLOSED`) |
| Reconciliation | **PASS** |
| promotion_lock | **false** |

---

## Command to view pipeline

```bash
python3 tae.py profit-pipeline
```

Or:

```bash
python3 tae.py morning-audit   # includes PROFIT PIPELINE section
```

---

## Remaining non-blocking notes

1. **0% order join in latest cycle** — full-paper-cycle produced decisions but execution skipped all as same action (no new `paper_orders` rows). Pipeline reports this honestly with inferred `same_action` buckets.
2. **Morning audit ATTENTION_REQUIRED** — global score 79 (infra/bot), not a pipeline data conflict.
