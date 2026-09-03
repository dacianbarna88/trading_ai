# TAE Executive Review — Pre-Build Audit

**Date:** 2026-07-22  
**Decision:** `SMALL_ORCHESTRATOR` (read-only consolidator; no new brain/governor/engine)

---

## Existing CLI commands (candidate / adjacent)

| Command | Module | Role |
|---------|--------|------|
| `health` | `tae_cli/commands/health.py` → `tae_quick_health_check.main()` | Operational health + advisory refresh (mutating) |
| `status` | `tae_cli/commands/status.py` | Lightweight process/git snapshot |
| `morning-audit` | `tae_morning_operational_audit.py` | Consolidated morning brief (closest prior art) |
| `full-paper-cycle` | `tae_full_paper_cycle.py` | PAPER closed loop (mutating orchestrator) |
| `investment-council` | `tae_investment_council.py` | Synthesis brief (paper-focused) |
| `decision-state-refresh` | `tae_decision_state.py` | PDE state builder (mutating) |
| `profit-pipeline` | `tae_profit_pipeline.py` | PAPER profit pipeline (mutating) |
| `canonical-vs-paper` | `tae_cli/commands/canonical_vs_paper.py` | Accounting vs paper compare |
| `30-day-paper-validation` | paper validation tracker | Validation milestones |

**None** expose a single three-part executive review (economic + architecture + operations).

---

## Reusable producers / artifacts

### A. Economic & profit

| Artifact | Producer | Canonical | Notes |
|----------|----------|-----------|-------|
| `tae_accounting_snapshot.json` | `tae_accounting_snapshot.py` | **Yes** | Capital base 30k, corrected PnL, winners/losers |
| `tae_profit_pipeline.json` | `tae_profit_pipeline.py` | **Yes** | Latest PAPER cycle economics |
| `tae_profit_optimization_audit.json` | `tae_profit_optimization.py` | **Yes** | Win rate, profit factor, drawdown (clean window) |
| `tae_baseline_vs_challengers.json` | profit optimization / ROI | **Yes** | Baseline vs challenger metrics |
| `tae_30_day_paper_profit_validation.json` | `30-day-paper-validation` CLI | **Yes** | Validation state (day 0 baseline) |
| `TAE_PROFIT_EDGE_DISCOVERY.md` | historical analysis | Reference | `NO_EDGE_FOUND` — not live SSOT |
| `tae_blocker_roi_report.json` | — | **Missing** | Not present in repo |

### B. Architecture & integration

| Artifact | Producer | Canonical | Notes |
|----------|----------|-----------|-------|
| `tae_quick_health_check.json` | `tae_quick_health_check.py` | **Yes** | Live ops + evidence chain |
| `tae_live_advisory.json` | `LiveAdvisoryBridge` via health / market-open | **Yes** | BUY gate source |
| `tae_decision_state_ownership_audit.json` | governance audit | **Yes** (static) | 2026-07-08 — historical reference |
| `tae_decision_governor.json` | `tae_decision_governor.py` | **Yes** | SHADOW_ONLY enrichment |
| `TAE_MASTER_STRATEGIC_REVIEW.md` | chapter record | Reference | Not runtime SSOT |
| `TAE_INTEGRATION_MATRIX.md` | audit | Reference | |
| `tae_unified_runtime.json` | legacy | **Stale** (2026-06-30) — must not present as live |

### C. Operations & institutional

| Artifact | Producer | Canonical | Notes |
|----------|----------|-----------|-------|
| `tae_quick_health_check.json` | health | **Yes** | Bot, dashboard, git, heartbeat |
| `tae_live_advisory.json` | advisory bridge | **Yes** | `block_new_buy` gate |
| `bot_output.log` | `live_bot.py` | **Yes** | Latest BUY/SELL evidence |
| `portfolio.csv` | `live_bot.py` | **Yes** | Positions (read-only) |
| `TAE_EXECUTIVE_VERDICT.md` | chapter synthesis | Reference | Institutional posture |
| `TAE_CHAPTER_7_INSTITUTIONAL_READINESS.md` | chapter record | Reference | |

---

## Closest existing orchestrator

**`tae_morning_operational_audit.py`** — READ_ONLY aggregator with freshness targets, JSON loading, markdown output.  
**Extend pattern:** new `tae_executive_review.py` as a focused three-lens consolidator (not a fork of morning audit).

---

## Real gaps

1. No single command combining economic + architecture + operations lenses.
2. `tae_blocker_roi_report.json` absent — use `tae_profit_optimization_audit.json` `top_blockers` instead.
3. `tae_decision_state_ownership_audit.json` is dated — must be labeled historical, not live state.
4. `tae_unified_runtime.json` must be explicitly rejected as stale live SSOT.
5. Economic edge requires cross-artifact synthesis (accounting + profit optimization + edge discovery).

---

## Integration decision

**`SMALL_ORCHESTRATOR`**

- New: `tae_executive_review.py` (read-only builder)
- New: `tae_cli/commands/executive_review.py` → delegates to `main()`
- Reuse: existing JSON/MD artifacts only; no subprocess to mutating pipelines
- Do **not** call `health` (mutates advisory); read current artifacts
- Required sources fail closed: `tae_quick_health_check.json`, `tae_live_advisory.json`, `tae_accounting_snapshot.json`

---

## Host evidence to include (commit `f426875`)

```
Quick Health (READY_WITH_WARNINGS / GENERATED_ARTIFACTS_ONLY)
  → Live Advisory refresh (post-health hook)
  → block_new_buy=False
  → BUY permis AIR.PA
  → BUY executat AIR.PA @ 207.90
```

Evidence paths: `tae_quick_health_check.json` → `evidence.buy_executat`, `evidence.tae_live_advisory`; `tae_live_advisory.json` → `block_new_buy`.
