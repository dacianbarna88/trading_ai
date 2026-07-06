# TAE Dependency Map — X.AUDIT

**Date:** 2026-07-06  
**Mode:** READ_ONLY

Legend: **Live impact** = YES (executes trades) · PARTIAL (gates BUY) · NO (shadow/report)

---

## 1. Live execution spine

### `live_bot.py`

| | |
|---|---|
| **Inputs** | `watchlist.txt`, yfinance, `live_signals.csv`, `portfolio.csv`, `tae_live_advisory.json` (via runtime) |
| **Outputs** | `portfolio.csv`, `live_signals.csv` |
| **Reads** | CSV, advisory JSON |
| **Writes** | CSV (trades) |
| **Upstream** | Scanner/scoring internal |
| **Downstream** | All accounting, shadow, dashboard |
| **Live impact** | **YES** |
| **Mode** | LIVE |

### `research_core/governance/live_advisory_runtime.py`

| | |
|---|---|
| **Inputs** | `tae_live_advisory.json` |
| **Outputs** | In-memory gate decision (consumed by live_bot) |
| **Live impact** | **PARTIAL** (blocks new BUY only) |
| **Mode** | ADVISORY |

---

## 2. Advisory spine

### `research_core/governance/advisory_index.py`

| | |
|---|---|
| **Inputs** | Unified runtime, committee, macro summaries |
| **Outputs** | `tae_advisory_index.json`, MD |
| **Live impact** | NO |
| **Mode** | ADVISORY |

### `research_core/governance/live_advisory_bridge.py`

| | |
|---|---|
| **Inputs** | Advisory index, unified runtime, optional `tae_decision_governor.json` (enrichment) |
| **Outputs** | `tae_live_advisory.json` |
| **Downstream** | `live_advisory_runtime.py`, dashboard |
| **Live impact** | **PARTIAL** (indirect via advisory) |
| **Mode** | ADVISORY |

### `research_core/governance/shadow_validation_ledger.py`

| | |
|---|---|
| **Inputs** | Live bot BUY path events |
| **Outputs** | `tae_shadow_validation_events.csv` |
| **Downstream** | `tae_shadow_outcome_capture.py`, reports |
| **Live impact** | NO (observes only) |
| **Mode** | SHADOW |

### `tae_shadow_outcome_capture.py` / `shadow_outcome_attribution.py`

| | |
|---|---|
| **Inputs** | `tae_shadow_validation_events.csv`, `portfolio.csv`, marks |
| **Outputs** | `tae_shadow_validation_outcomes.json`, MD |
| **Live impact** | NO |
| **Mode** | SHADOW / REPORT_ONLY |

---

## 3. Market-open shadow stack

### `market_open_runner.sh` → `tae_market_open_intelligence_runner.py`

| Step | Script | Reads | Writes | Live | Mode |
|------|--------|-------|--------|------|------|
| 1 | `tae_infrastructure_health.py` | LaunchAgent, cron | JSON, MD | NO | SHADOW |
| 2 | `tae_intraday_fade_intelligence.py` | portfolio.csv, fade data | JSON, MD | NO | SHADOW |
| 3 | `tae_intraday_fade_history.py` | fade JSON | CSV, summary JSON | NO | SHADOW |
| 4 | `tae_intraday_discovery_engine.py` | history CSV | JSON, MD | NO | SHADOW |
| 5 | `tae_profit_protection_shadow.py` | portfolio.csv, fade, knowledge | JSON, MD | NO | SHADOW |
| 6 | `tae_profit_protection_validation.py` | fade history CSV | JSON, MD | NO | SHADOW |
| 7 | `tae_stop_reentry_cooldown_audit.py` | portfolio.csv | JSON, MD | NO | SHADOW |
| 8 | `tae_decision_replay_composer.py` | accounting, portfolio, fade | JSON, MD | NO | SHADOW |
| 9 | `tae_confidence_evolution.py` | replay, signals | JSON, MD | NO | SHADOW |
| 10 | `tae_knowledge_base.py` | protect, cooldown, replay, confidence | JSON, MD | NO | SHADOW |
| 11 | `tae_decision_governor.py` | unified, advisory, replay, knowledge, … | JSON, MD | NO | SHADOW |

**Orchestrator outputs:** `tae_market_open_intelligence_runner.json`, `.md`

---

## 4. Profit intelligence spine (`tae.py protect`)

| Step | Script | Reads | Writes | Live | Mode |
|------|--------|-------|--------|------|------|
| 1 | `tae_profit_protection_shadow.py` | portfolio.csv, fade, knowledge | JSON, MD | NO | SHADOW |
| 2 | `tae_profit_intelligence_brain.py` | shadow JSON | JSON, MD | NO | SHADOW |
| 3 | `tae_profit_memory_engine.py` | brain, shadow, portfolio | JSON, MD | NO | SHADOW |
| 4 | `tae_profit_decision_committee.py` | shadow, brain, memory, validation | JSON, MD | NO | SHADOW |
| 5 | `tae_profit_committee_learning.py` | committee, memory | JSON, MD | NO | SHADOW |
| 6 | `tae_profit_context_engine.py` | committee, learning, signals, regime | JSON, MD, learning JSON | NO | SHADOW |
| 7 | `tae_profit_decision_governor.py` | committee, context, shadow | JSON, MD | NO | SHADOW |

### `tae.py portfolio-protect`

| Step | Script | Reads | Writes |
|------|--------|-------|--------|
| 1 (if stale) | `tae_profit_decision_governor.py` | upstream profit JSON | governor JSON |
| 2 | `tae_portfolio_profit_governor.py` | governor, context, shadow, portfolio.csv | JSON, MD |

### `tae.py policy`

| Step | Script | Reads | Writes |
|------|--------|-------|--------|
| 1 (if stale) | `tae_portfolio_profit_governor.py` | governor + sources | PPG JSON |
| 2 | `tae_adaptive_profit_policy_engine.py` | PPG JSON (+ prior APPE history) | JSON, MD |

---

## 5. Accounting spine

### `tae_accounting_snapshot.py` → `research_core/accounting/accounting_snapshot.py`

| | |
|---|---|
| **Inputs** | `portfolio.csv` (read-only), capital base rules |
| **Outputs** | `tae_accounting_snapshot.json`, `.md`, capital integrity audit |
| **Downstream** | replay composer, dashboard, ecosystem review |
| **Live impact** | NO |
| **Mode** | REPORT_ONLY (canonical PnL SSOT) |

### `tae_portfolio_reconciliation.py`

| | |
|---|---|
| **Inputs** | `portfolio.csv` |
| **Outputs** | `tae_portfolio_reconciliation.json`, execution integrity audit |
| **Live impact** | NO |
| **Mode** | REPORT_ONLY |

---

## 6. Unified runtime & enrichers

### `tae_unified_runtime.py`

| | |
|---|---|
| **Inputs** | Multiple runtime JSON fragments |
| **Outputs** | `tae_unified_runtime.json` |
| **Downstream** | advisory bridge, governor, enrichers |
| **Mode** | SHADOW / ADVISORY feed |

### `tae_live_signals_*_enrich.py` (5 modules)

| | |
|---|---|
| **Inputs** | `live_signals.csv`, various runtime JSON |
| **Outputs** | Enriched signal columns / side files |
| **Live impact** | NO (feeds scanner refresh chain) |
| **Mode** | SHADOW |

---

## 7. CLI / operations

### `tae.py` dispatcher

| Command | Invokes | Live impact |
|---------|---------|-------------|
| `health` | `tae_quick_health_check.py` | NO |
| `protect` | 7-step profit stack | NO |
| `portfolio-protect` | PPG (+ PDG if stale) | NO |
| `policy` | APPE (+ PPG if stale) | NO |
| `status` | status readers | NO |
| `help` | banner | NO |

---

## 8. Cross-spine dependency diagram

```
watchlist.txt ──► live_bot.py ──► portfolio.csv / live_signals.csv
                      ▲                    │
                      │                    ├──► accounting_snapshot (SSOT PnL)
              tae_live_advisory.json       ├──► profit_protection_shadow
                      ▲                    ├──► intraday_fade_intelligence
         live_advisory_bridge              └──► shadow_validation_ledger
                      ▲
         tae_advisory_index / unified_runtime

market_open_runner ──► intelligence_runner (11 steps) ──► tae_decision_governor.json
                                                              (enrichment only)

tae.py protect ──► profit stack (7) ──► tae_profit_decision_governor.json
tae.py portfolio-protect ──► tae_portfolio_profit_governor.json
tae.py policy ──► tae_adaptive_profit_policy_engine.json
```

---

## 9. Critical artifact producers

| Artifact | Primary producer | Consumers |
|----------|------------------|-----------|
| `portfolio.csv` | `live_bot.py` | Everything (read-only elsewhere) |
| `tae_accounting_snapshot.json` | accounting_snapshot | replay, dashboard, reviews |
| `tae_live_advisory.json` | live_advisory_bridge | live_bot gate, dashboard |
| `tae_decision_governor.json` | tae_decision_governor | bridge enrichment, dashboard |
| `tae_profit_decision_governor.json` | profit decision governor | PPG, APPE |
| `tae_portfolio_profit_governor.json` | portfolio profit governor | APPE |
| `tae_knowledge_base.json` | tae_knowledge_base | protect shadow, governor |

---

**READ_ONLY audit — no files modified.**
