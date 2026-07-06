# TAE Master SSOT Registry

**Version:** v1  
**Effective:** 2026-07-06  
**Authority:** Single reference for field ownership — update on any new SSOT  
**Sources:** `TAE_SSOT_AUDIT.md`, X.AUDIT consolidation, codebase inspection

---

## Registry rules

1. **One owner per field** — consumers read, never redefine
2. **Only `live_bot.py` writes** trade ledger and signals CSV
3. **Accounting snapshot** is the only authoritative PnL for TAE reports
4. **Shadow modules** emit JSON/MD — never mutate live SSOTs
5. **New fields** require sprint report + registry update before merge

---

## Master registry

### Execution & ledger

| Field | SSOT owner | Artifact / module | Secondary consumers | Duplicate risk | Recommended rule |
|-------|------------|-------------------|---------------------|----------------|------------------|
| **trade ledger** | `live_bot.py` | `portfolio.csv` | accounting, all shadow, dashboard | FIFO parsers recompute | **Write:** live_bot only. **Read:** prefer shared parser |
| **portfolio positions** | `live_bot.py` → `portfolio.csv` | CSV rows | protect, fade, PPG, replay | dashboard, shadow (each own parser) | **EXTEND** shared read-only position reader |
| **cash** | `research_core/accounting/accounting_snapshot.py` | `tae_accounting_snapshot.json` | dashboard, replay | dashboard cash calc | **REUSE** snapshot `cash_available` |
| **live buy/sell execution** | `live_bot.py` | `portfolio.csv` actions | reconciliation audit | none | **Never** shadow execute |

### Accounting / PnL

| Field | SSOT owner | Artifact | Secondary consumers | Duplicate risk | Recommended rule |
|-------|------------|----------|---------------------|----------------|------------------|
| **corrected_pnl** | `accounting_snapshot.py` | `corrected_total_trading_pnl` in JSON | ecosystem review, replay | raw CSV sums | **REUSE** snapshot only in new modules |
| **realized_pnl** | `accounting_snapshot.py` | `corrected_realized_pnl` | replay, dashboard | cooldown local leg calc | **REUSE** snapshot; mark local as diagnostic |
| **unrealized_pnl** | `accounting_snapshot.py` | `corrected_unrealized_pnl` | dashboard | live_bot MTM | **REUSE** for reports |
| **account_value** | `accounting_snapshot.py` | `account_value_corrected` | dashboard, capital audit | capital-based variant | **REUSE** corrected field as canonical |

### Advisory & live gate

| Field | SSOT owner | Artifact | Secondary consumers | Duplicate risk | Recommended rule |
|-------|------------|----------|---------------------|----------------|------------------|
| **live advisory state** | `live_advisory_bridge.py` | `tae_live_advisory.json` | `live_advisory_runtime.py`, dashboard | advisory index (upstream) | **Runtime reads** live_advisory.json only |
| **shadow validation events** | `shadow_validation_ledger.py` | `tae_shadow_validation_events.csv` | X.10 capture, reports | none | **Append-only** log |
| **market session state** | `market_session_guard.py` | internal / status | market_open_runner | infra health (process) | **KEEP_SEPARATE** session vs infra |

### Profit protection stack

| Field | SSOT owner | Artifact | Secondary consumers | Duplicate risk | Recommended rule |
|-------|------------|----------|---------------------|----------------|------------------|
| **profit protection state** | `tae_profit_protection_shadow.py` | `tae_profit_protection_shadow.json` | PIB, PDC, PDG, market-open step 5 | validation JSON (gates) | **REUSE** shadow JSON |
| **profit survival probability** | `tae_profit_intelligence_brain.py` | `tae_profit_intelligence_brain.json` | PCE, PDC, memory | none | **REUSE** PSP fields |
| **profit memory** | `tae_profit_memory_engine.py` | `tae_profit_memory_engine.json` | PDC, learning, PCE | committee learning ground truth | **REUSE** episodes; stable `episode_key` |
| **profit context score** | `tae_profit_context_engine.py` | `tae_profit_context_engine.json` | PDG, reports | none (v1 removed) | **REUSE** PCE output |
| **profit decision (ticker)** | `tae_profit_decision_committee.py` | votes in committee JSON | PDG | v1 vs weighted rec | **Display SSOT:** PDG; **vote SSOT:** PDC |
| **profit decision governor** | `tae_profit_decision_governor.py` | `tae_profit_decision_governor.json` | PPG, APPE | global decision governor | **KEEP_SEPARATE** from `tae_decision_governor` |
| **portfolio profit governor** | `tae_portfolio_profit_governor.py` | `tae_portfolio_profit_governor.json` | APPE, reports | none | **REUSE** portfolio verdict |
| **adaptive profit policy** | `tae_adaptive_profit_policy_engine.py` | `tae_adaptive_profit_policy_engine.json` | future knowledge ingest | knowledge recommendations | **REUSE** APPE observations |

### Knowledge & confidence

| Field | SSOT owner | Artifact | Secondary consumers | Duplicate risk | Recommended rule |
|-------|------------|----------|---------------------|----------------|------------------|
| **knowledge base** | `tae_knowledge_base.py` | `tae_knowledge_base.json` | protect, governor, reports | source modules | **VIEW only** — ingest, don't duplicate logic |
| **confidence evolution** | `tae_confidence_evolution.py` | `tae_confidence_evolution.json` | knowledge base | PDC "confidence" naming | **Prefix:** `signal_confidence` vs profit confidence |

### Learning weights

| Field | SSOT owner | Artifact | Secondary consumers | Duplicate risk | Recommended rule |
|-------|------------|----------|---------------------|----------------|------------------|
| **committee member weights** | `tae_profit_committee_learning.py` | `tae_profit_committee_learning.json` | PDC weighted tickers | none | **REUSE** learning JSON |
| **context component weights** | PCE v2 / context learning | `tae_profit_context_learning.json` | PCE scoring | none | **REUSE** context learning |

### Global decision (non-profit)

| Field | SSOT owner | Artifact | Secondary consumers | Duplicate risk | Recommended rule |
|-------|------------|----------|---------------------|----------------|------------------|
| **global advisory posture** | `tae_decision_governor.py` | `tae_decision_governor.json` | advisory bridge enrichment | profit PDG | **KEEP_SEPARATE** scopes |
| **unified runtime (ticker)** | `tae_unified_runtime.py` | `tae_unified_runtime.json` | bridge, enrichers | scanner refresh legacy | **REUSE** unified runtime reader |

### Operations & meta

| Field | SSOT owner | Artifact | Secondary consumers | Duplicate risk | Recommended rule |
|-------|------------|----------|---------------------|----------------|------------------|
| **dashboard state** | `dashboard_v2.py` | reads CSV/JSON | user | recomputes PnL | **Migrate** to accounting snapshot reads |
| **CLI commands** | `tae.py` → `tae_cli/dispatcher.py` | command registry | help | standalone scripts | **Register** all user-facing flows in CLI |
| **project roadmap** | `TAE_MASTER_ROADMAP.md` | this file | SESSION_START, PROJECT_BOOK | TAE_ROADMAP.md legacy | **MASTER_ROADMAP** is forward authority |
| **project status** | `PROJECT_STATUS.md`, `PROJECT_BOOK.md` | docs | SESSION_START | multiple status files | **Sync** on major sprint completion |

---

## Confidence naming standard (avoid collision)

| Name in docs | SSOT module | Meaning |
|--------------|-------------|---------|
| `signal_confidence` | confidence evolution | Pre-entry score decay |
| `profit_decision_confidence` | PDC / PCE / PDG | Post-entry protect confidence |
| `advisory_confidence` | live advisory JSON | Live gate confidence |
| `policy_accuracy` | APPE | Portfolio policy validation rate |

---

## Write permission matrix

| Artifact | Writers | Readers |
|----------|---------|---------|
| `portfolio.csv` | `live_bot.py` | all (read-only) |
| `live_signals.csv` | `live_bot.py` | scanner, enrichers, confidence |
| `tae_accounting_snapshot.json` | `tae_accounting_snapshot.py` | all reports |
| `tae_live_advisory.json` | `live_advisory_bridge.py` | live_bot gate, dashboard |
| Profit stack JSON | respective `tae_profit_*.py` | downstream VIEW composers |
| `tae_knowledge_base.json` | `tae_knowledge_base.py` | protect, governor |

---

## Update log

| Date | Change | Sprint |
|------|--------|--------|
| 2026-07-06 | v1 registry created from X.AUDIT | MASTER ECOSYSTEM AUDIT v1 |

---

**Governance document — no code changes.**
