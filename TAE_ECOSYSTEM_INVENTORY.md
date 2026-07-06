# TAE Ecosystem Inventory — X.AUDIT

**Date:** 2026-07-06  
**Mode:** READ_ONLY · NO_BROKER · NO_EXECUTION · NO_COMMIT  
**Checkpoint reference:** `1b40d6e` — adaptive decision and portfolio governors

---

## Executive summary

TAE at `~/Desktop/trading_ai` contains **~267 root Python modules**, **155 `tae*.py` scripts**, **114+ TAE markdown artifacts**, and a **`research_core/`** package. The ecosystem splits into **five operational spines**:

1. **Live execution** — `live_bot.py`, CSV SSOTs, session guard
2. **Advisory runtime** — bridge → live advisory → BUY gate
3. **Market-open shadow stack** — 11-step intelligence runner
4. **Profit intelligence stack** — 10-module protect / governor / policy CLI chain (new)
5. **Accounting / research batch** — snapshot, reconciliation, ecosystem orchestrator

Most new profit modules are **SHADOW_ONLY** and **not wired to live execution**.

---

## Inventory by category

### LIVE_RUNTIME

| Component | Path | Role |
|-----------|------|------|
| Live bot | `live_bot.py` | Canonical BUY/SELL/STOP execution |
| Bot controller | `bot_controller.py` | Start/stop bot and dashboard |
| Session guard | `market_session_guard.py` | Market-hours gate |
| Portfolio SSOT | `portfolio.csv` | Trade ledger (protected) |
| Signals SSOT | `live_signals.csv` | Scanner output (protected) |
| Watchlist | `watchlist.txt` | Bot universe (protected) |
| Core trades | `core/trades.py`, `core/portfolio.py` | Shared trade helpers (protected) |
| Config | `config/settings.py` | Starting capital, paths |

### ADVISORY_RUNTIME

| Component | Path | Role |
|-----------|------|------|
| Advisory index | `research_core/governance/advisory_index.py` | Builds `tae_advisory_index.json` |
| Live advisory bridge | `research_core/governance/live_advisory_bridge.py` | Builds `tae_live_advisory.json` |
| Live advisory runtime | `research_core/governance/live_advisory_runtime.py` | **X.8** — blocks new BUY on `RISK_ADVISORY` |
| Shadow validation ledger | `research_core/governance/shadow_validation_ledger.py` | BUY path event log (X.9) |
| Shadow outcome attribution | `research_core/governance/shadow_outcome_attribution.py` | X.10 outcome closure engine |
| Outcome capture CLI | `tae_shadow_outcome_capture.py` | Batch outcome attribution runner |

### SHADOW_RUNTIME (market-open stack)

| Component | Path | Role |
|-----------|------|------|
| Market open shell | `market_open_runner.sh` | Awake guard, bot, dashboard, intelligence |
| Intelligence runner | `tae_market_open_intelligence_runner.py` | 11-step SHADOW pipeline |
| Infrastructure health | `tae_infrastructure_health.py` | Autostart / cron audit |
| Intraday fade | `tae_intraday_fade_intelligence.py` | Fade detection |
| Fade history | `tae_intraday_fade_history.py` | Historical fade CSV |
| Discovery engine | `tae_intraday_discovery_engine.py` | Pattern discovery |
| Profit protection (snapshot) | `tae_profit_protection_shadow.py` | Rules v1 shadow advisories |
| Profit validation | `tae_profit_protection_validation.py` | Historical strategy gates |
| Cooldown audit | `tae_stop_reentry_cooldown_audit.py` | STOP→reentry churn |
| Decision replay | `tae_decision_replay_composer.py` | Sequencing attribution |
| Confidence evolution | `tae_confidence_evolution.py` | Score decay hypotheses |
| Knowledge base | `tae_knowledge_base.py` | Consolidated learning VIEW |
| Decision governor | `tae_decision_governor.py` | Cross-domain advisory VIEW |
| Unified runtime | `tae_unified_runtime.py` | Per-ticker SSOT merge |
| Scanner refresh | `tae_scanner_refresh.py` | Legacy runtime chain |

### PROFIT_INTELLIGENCE (protect CLI stack)

| Component | Path | Role |
|-----------|------|------|
| Protection shadow | `tae_profit_protection_shadow.py` | Rules v1 per-position shadow |
| Intelligence brain / PSP | `tae_profit_intelligence_brain.py` | Survival / giveback scoring |
| Memory engine | `tae_profit_memory_engine.py` | Episode memory + dedupe |
| Decision committee | `tae_profit_decision_committee.py` | Multi-member votes |
| Committee learning | `tae_profit_committee_learning.py` | Adaptive member weights |
| Context engine | `tae_profit_context_engine.py` | Adaptive weighted context (v2) |
| Context learning | `tae_profit_context_learning.json` | Component weight persistence |
| Profit decision governor | `tae_profit_decision_governor.py` | PDC + PCE reconciliation VIEW |
| Adaptive policy engine | `tae_adaptive_profit_policy_engine.py` | Policy memory + evaluation |

### PORTFOLIO_INTELLIGENCE

| Component | Path | Role |
|-----------|------|------|
| Portfolio profit governor | `tae_portfolio_profit_governor.py` | Portfolio-level verdict |
| Portfolio reconciliation | `tae_portfolio_reconciliation.py` | SELL integrity read-only |
| Independent position risk | (research_core) | Per-position risk views |
| Full ecosystem review | `tae_full_ecosystem_review.py` | Batch portfolio analytics |

### ACCOUNTING

| Component | Path | Role |
|-----------|------|------|
| Accounting snapshot CLI | `tae_accounting_snapshot.py` | Emits `tae_accounting_snapshot.json` |
| Accounting core | `research_core/accounting/accounting_snapshot.py` | **PnL SSOT builder** |
| Capital base integrity | `research_core/accounting/capital_base_integrity.py` | Deposit / capital audit |
| Execution integrity | `research_core/accounting/execution_integrity.py` | SELL reconciliation |
| Consistency check | `tae_accounting_consistency_check.py` | Cross-check reports |

### DECISION

| Component | Path | Role |
|-----------|------|------|
| Decision governor (global) | `tae_decision_governor.py` | Market-open VIEW composer |
| Profit decision governor | `tae_profit_decision_governor.py` | Profit-stack VIEW composer |
| Decision replay | `tae_decision_replay_composer.py` | Failure mode attribution |
| Committee runtime | `tae_committee_runtime.py` | Strategic committee (legacy path) |
| Weighted committee | `weighted_committee_decision.txt` | Macro committee output |

### KNOWLEDGE

| Component | Path | Role |
|-----------|------|------|
| Knowledge base | `tae_knowledge_base.py` | Materialized VIEW over shadow outputs |
| Knowledge summary | `tae_knowledge_summary.md` | Human report |
| Event memory runtime | `tae_event_memory_runtime.py` | Scaffold — low ingestion |
| Learning runtime | `tae_learning_runtime.py` | Research learning scaffold |

### LEARNING

| Component | Path | Role |
|-----------|------|------|
| Committee learning | `tae_profit_committee_learning.py` | Member accuracy weights |
| Context learning | (embedded in PCE v2) | Context component weights |
| Adaptive profit policy | `tae_adaptive_profit_policy_engine.py` | Portfolio policy memory |
| Confidence evolution | `tae_confidence_evolution.py` | Score decay learning |

### RESEARCH

| Component | Path | Role |
|-----------|------|------|
| Full ecosystem run | `tae_full_ecosystem_run.py` | Batch evidence pipeline |
| Ecosystem orchestrator | `research_core/ecosystem_orchestrator.py` | Multi-phase research |
| Phase demos | `tae_phase*_demo.py` (40+) | Historical sprint demos |
| Strategy discovery/sim | `tae_strategy_*_runtime.py` | Simulation scaffolds |
| Candidate queue | `tae_candidate_queue_builder.py` | Promotion candidates |
| Watchlist proposal | `tae_watchlist_proposal.py` | Watchlist research |

### INFRASTRUCTURE

| Component | Path | Role |
|-----------|------|------|
| Quick health check | `tae_quick_health_check.py` | Daily ecosystem health |
| Startup launcher | `tae_startup_launcher.py` | Boot sequence |
| Startup verify | `tae_startup_verify.py` | Post-start validation |
| Infrastructure health | `tae_infrastructure_health.py` | LaunchAgent / cron audit |
| Market open monitor | `tae_market_open_monitor.py` | Runner monitoring |
| Awake guard | `awake_guard.sh` | Keep-alive shell |

### CLI

| Component | Path | Role |
|-----------|------|------|
| TAE CLI entry | `tae.py` | Command center dispatcher |
| CLI package | `tae_cli/` | `health`, `protect`, `portfolio-protect`, `policy`, `status`, `help` |
| Protect pipeline | `tae_cli/commands/protect.py` | 7-step profit shadow stack |
| Portfolio-protect | `tae_cli/commands/portfolio_protect.py` | PPG refresh |
| Policy | `tae_cli/commands/policy.py` | APPE refresh |

### DASHBOARD

| Component | Path | Role |
|-----------|------|------|
| Dashboard v2 | `dashboard_v2.py` | Streamlit main UI |
| TAE command center tab | `dashboard_tae_command_center.py` | TAE reports in dashboard |

### VALIDATION

| Component | Path | Role |
|-----------|------|------|
| Shadow validation report | `tae_shadow_validation_report.py` | Event summaries |
| Profit protection validation | `tae_profit_protection_validation.py` | Strategy backtest gates |
| Shadow outcome capture | `tae_shadow_outcome_capture.py` | X.10 batch |
| Various `*_test.py` | 20+ modules | Unit tests |

### REPORT_ONLY

| Component | Examples |
|-----------|----------|
| Sprint reports | `TAE_*_REPORT.md` (114 files) |
| Audits | `TAE_*_AUDIT.md`, `TAE_10_DAY_TRADING_AUDIT.md` |
| Architecture docs | `TAE_ARCHITECTURE.md`, `PROJECT_BOOK.md` |

### LEGACY

| Component | Notes |
|-----------|-------|
| `live_bot_v5_1.py` | Superseded by `live_bot.py` |
| `daily_intelligence_runner.py` | Pre-governance daily runner |
| Root `outcome_assignment_engine.py` | V14-era, not X.9 schema |
| `tae_scanner_refresh.py` chain | Pre-unified-runtime path |
| `tae_phase*_demo.py` | Sprint demos — not production spines |
| V14 threshold / regional stacks | Under `engine/` legacy paths |

### UNKNOWN / ORPHAN

| Pattern | Notes |
|---------|-------|
| Duplicate profit paths | Market-open step 5–6 vs full `tae.py protect` stack |
| Dual governors | `tae_decision_governor` vs `tae_profit_decision_governor` |
| Multiple runtime builders | `tae_*_runtime.py` (12+) — enrichment chain, unclear live use |

---

## Required components — status

| Required | Category | Status |
|----------|----------|--------|
| `live_bot.py` | LIVE_RUNTIME | ✅ Canonical |
| `tae.py` | CLI | ✅ Active (6 commands) |
| `tae_cli/` | CLI | ✅ Active |
| `tae_quick_health_check.py` | INFRASTRUCTURE | ✅ Active |
| `market_open_runner.sh` | INFRASTRUCTURE | ✅ Active |
| `tae_accounting_snapshot.py` | ACCOUNTING | ✅ PnL SSOT |
| `tae_portfolio_reconciliation.py` | ACCOUNTING | ✅ Read-only |
| Profit stack (10 modules) | PROFIT_INTELLIGENCE | ✅ SHADOW mature |
| `research_core/governance/` | ADVISORY_RUNTIME | ✅ Active |

---

## Scale metrics

| Metric | Count |
|--------|-------|
| Root `*.py` | ~267 |
| `tae*.py` | ~155 |
| TAE markdown reports | ~114 |
| Market-open pipeline steps | 11 |
| Protect CLI pipeline steps | 7 |
| CLI commands | 6 |

---

**READ_ONLY audit — no files modified.**
