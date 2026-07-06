# TAE Master Architecture — X.AUDIT

**Date:** 2026-07-06  
**Mode:** READ_ONLY

Legend: 🟢 canonical · 🟡 shadow-only · 🔵 report-only · ⚫ legacy

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LIVE EXECUTION SPINE 🟢                               │
│  watchlist.txt → live_bot.py → portfolio.csv + live_signals.csv             │
│       ↑                                                                        │
│       └── live_advisory_runtime ← tae_live_advisory.json 🟡                   │
└─────────────────────────────────────────────────────────────────────────────┘
         │ read-only                           │ events
         ▼                                     ▼
┌──────────────────────┐              ┌──────────────────────┐
│ ACCOUNTING SPINE 🔵   │              │ SHADOW OBSERVABILITY  │
│ accounting_snapshot  │              │ shadow_validation_    │
│ reconciliation       │              │ ledger → X.10 capture │
└──────────────────────┘              └──────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ADVISORY SPINE 🟡 (live-connected)                       │
│  advisory_index → live_advisory_bridge → tae_live_advisory.json             │
│       ↑ optional enrichment: tae_decision_governor.json                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│              MARKET-OPEN SHADOW SPINE 🟡 (11 steps, daily)                   │
│  infrastructure → intraday fade → discovery → protect snapshot →           │
│  validation → cooldown → replay → confidence → knowledge →                 │
│  tae_decision_governor (global VIEW)                                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│              PROFIT INTELLIGENCE SPINE 🟡 (CLI on demand)                  │
│  protect: shadow → PSP → memory → committee → learning → context → PDG    │
│  portfolio-protect: PPG                                                      │
│  policy: APPE                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│              RESEARCH / BATCH SPINE 🔵 (offline)                             │
│  tae_full_ecosystem_run, phase demos ⚫, strategy simulation scaffolds       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│              CLI / OPS SPINE 🟢                                              │
│  tae.py: health | protect | portfolio-protect | policy | status | help      │
│  market_open_runner.sh | bot_controller | infrastructure_health             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│              DASHBOARD SPINE 🟢/🔵                                           │
│  dashboard_v2.py + dashboard_tae_command_center (reads JSON/CSV only)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Spine details

### 1. Live execution spine (CANONICAL)

| Module | Type | Writes live state |
|--------|------|-------------------|
| `live_bot.py` | 🟢 canonical | YES — only trade writer |
| `portfolio.csv` | 🟢 SSOT | YES (via live_bot) |
| `live_signals.csv` | 🟢 SSOT | YES (via live_bot) |
| `core/trades.py` | 🟢 shared | Called by live_bot |
| `market_session_guard.py` | 🟢 gate | NO |

**Rule:** No shadow module writes here.

### 2. Advisory spine (LIVE-CONNECTED, PARTIAL IMPACT)

| Module | Type | Live impact |
|--------|------|-------------|
| `advisory_index.py` | 🟡 shadow producer | NO |
| `live_advisory_bridge.py` | 🟡 composer | NO |
| `tae_live_advisory.json` | 🟡 SSOT | Indirect |
| `live_advisory_runtime.py` | 🟢 gate consumer | PARTIAL — blocks BUY |
| `tae_decision_governor.json` | 🟡 VIEW | Enrichment only |

### 3. Shadow intelligence spine (MARKET OPEN)

| Module | Type |
|--------|------|
| `tae_market_open_intelligence_runner.py` | 🟡 orchestrator |
| Steps 1–10 | 🟡 engines |
| `tae_decision_governor.py` | 🟡 materialized VIEW |
| `tae_knowledge_base.json` | 🟡 VIEW (not SSOT) |

**Does not** run profit committee stack (separate CLI).

### 4. Profit intelligence spine (ON-DEMAND)

| Module | Output | Type |
|--------|--------|------|
| `tae_profit_protection_shadow.py` | rules, missed USD | 🟡 |
| `tae_profit_intelligence_brain.py` | PSP scores | 🟡 |
| `tae_profit_memory_engine.py` | episodes | 🟡 |
| `tae_profit_decision_committee.py` | votes + weighted rec | 🟡 |
| `tae_profit_committee_learning.py` | member weights | 🟡 |
| `tae_profit_context_engine.py` | context score | 🟡 |
| `tae_profit_decision_governor.py` | ticker reconcile VIEW | 🟡 |
| `tae_portfolio_profit_governor.py` | portfolio verdict | 🟡 |
| `tae_adaptive_profit_policy_engine.py` | policy memory | 🟡 |

**CLI entry:** `tae.py protect` → `portfolio-protect` → `policy`

### 5. Portfolio intelligence spine

| Module | Scope | Type |
|--------|-------|------|
| `tae_portfolio_profit_governor.py` | Profit posture aggregation | 🟡 |
| `tae_portfolio_reconciliation.py` | SELL integrity | 🔵 |
| `tae_full_ecosystem_review.py` | Batch analytics | 🔵 |

### 6. Accounting spine (REPORT SSOT)

| Module | Type |
|--------|------|
| `research_core/accounting/accounting_snapshot.py` | 🟢 PnL SSOT builder |
| `tae_accounting_snapshot.json` | 🔵 canonical output |
| Capital / execution integrity audits | 🔵 |

### 7. CLI / operations spine

| Command | Pipeline | Type |
|---------|----------|------|
| `health` | quick health check | 🟢 |
| `protect` | 7-step profit stack | 🟡 |
| `portfolio-protect` | PDG + PPG | 🟡 |
| `policy` | PPG + APPE | 🟡 |
| `status` | read status files | 🟢 |
| `market_open_runner.sh` | live + shadow daily | 🟢 ops |

### 8. Knowledge / learning spine

| Module | Role | Type |
|--------|------|------|
| `tae_knowledge_base.py` | Cross-domain VIEW | 🟡 |
| `tae_confidence_evolution.py` | Signal decay | 🟡 |
| `tae_profit_committee_learning.py` | Member weights | 🟡 |
| `tae_profit_context_learning.json` | Context weights | 🟡 |
| `tae_adaptive_profit_policy_engine.py` | Policy memory | 🟡 |
| `tae_learning_runtime.py` | Scaffold | ⚫ legacy |

---

## Module classification summary

| Classification | Count (approx) | Examples |
|----------------|----------------|----------|
| 🟢 Canonical live/ops | ~10 | live_bot, bot_controller, session guard, CLI dispatcher |
| 🟡 Shadow-only | ~35 active | profit stack, market-open stack, governors |
| 🔵 Report-only | ~25 | accounting, reconciliation, audits, reports |
| ⚫ Legacy / demo | ~80+ | phase demos, old bots, V14 engines |

---

## Data flow — profit decision (canonical shadow path)

```
portfolio.csv (read)
       │
       ▼
tae_profit_protection_shadow.json
       ├──► tae_profit_intelligence_brain.json (PSP)
       │         └──► tae_profit_memory_engine.json
       │                   └──► tae_profit_decision_committee.json
       │                             └──► tae_profit_committee_learning.json
       │                                       └──► tae_profit_context_engine.json
       │                                                 └──► tae_profit_decision_governor.json
       │                                                           └──► tae_portfolio_profit_governor.json
       │                                                                     └──► tae_adaptive_profit_policy_engine.json
       └──► tae_profit_protection_validation.json (parallel gates)
```

---

## Boundaries (must hold for Profit Growth)

1. **Shadow spines never write** `portfolio.csv`, `live_signals.csv`, or execute orders.
2. **Accounting snapshot** is the only PnL authority for new modules.
3. **Two governors** serve different scopes — do not merge.
4. **APPE / PPG** do not connect to `live_advisory_runtime` without explicit promotion sprint.
5. **Profit Growth** modules slot **after** analytics SSOT, **before** any live policy change.

---

**READ_ONLY audit — no files modified.**
