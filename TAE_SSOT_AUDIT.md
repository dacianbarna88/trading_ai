# TAE SSOT Audit — X.AUDIT

**Date:** 2026-07-06  
**Mode:** READ_ONLY

For each critical field: **owner**, **consumers**, **duplicates**, **risk**, **recommended action**.

---

## Summary matrix

| Field | SSOT owner | Secondary consumers | Duplicate calculators | Risk | Action |
|-------|------------|---------------------|----------------------|------|--------|
| `corrected_pnl` | `research_core/accounting/accounting_snapshot.py` → `tae_accounting_snapshot.json` | replay composer, dashboard, ecosystem review | Raw `portfolio.csv` PnL column sums | **HIGH** if dashboard uses raw | **REUSE** accounting snapshot only |
| `realized_pnl` | Same (`corrected_realized_pnl`) | replay, phase demos, cooldown audit (local leg calc) | Legacy portfolio row sums | MEDIUM | **REUSE** SSOT; mark local calcs as diagnostic |
| `unrealized_pnl` | Same (`corrected_unrealized_pnl`) | dashboard, replay | `live_bot` mark-to-market, dashboard open positions | MEDIUM | **REUSE** SSOT for reporting; live bot for execution |
| `account_value` | Same (`account_value_corrected`) | dashboard, capital integrity | Cash-based vs capital-based variants in snapshot | LOW (documented) | **KEEP** snapshot as owner; expose one canonical field |
| `portfolio_positions` | `portfolio.csv` (written by `live_bot.py` only) | All shadow modules (read-only), accounting | FIFO parsers in dashboard, fade, protect (each reimplements) | **HIGH** drift if parsers diverge | **EXTEND** shared read-only position parser in `research_core` |
| `profit_at_risk` | `tae_profit_protection_shadow.json` (`rules_v1.profit_at_risk`) | PIB, PDC, PDG | PIB urgency flags, committee rules vote | MEDIUM overlap | **REUSE** shadow as owner; others reference flags |
| `profit_survival_probability` | `tae_profit_intelligence_brain.json` (PSP) | PCE, PDC, memory | None canonical elsewhere | LOW | **KEEP** PIB as SSOT |
| `profit_memory` | `tae_profit_memory_engine.json` (episodes + bias) | PDC, PCE, committee learning | Committee learning ground truth uses episodes | LOW | **KEEP** memory engine as SSOT |
| `profit_context_score` | `tae_profit_context_engine.json` | PDG, PPG (indirect) | None (v1 additive removed) | LOW | **KEEP** PCE as SSOT |
| `profit_decision` | **Split:** ticker = `tae_profit_decision_committee.json`; reconciled = `tae_profit_decision_governor.json` | PPG, dashboard | v1 vs weighted committee recs | **HIGH** confusion | **DOCUMENT** PDG as display SSOT; PDC as vote SSOT |
| `portfolio_profit_verdict` | `tae_portfolio_profit_governor.json` | APPE | None | LOW | **KEEP** PPG as SSOT |
| `adaptive_policy` | `tae_adaptive_profit_policy_engine.json` | None live | Suggested policies in knowledge base (different scope) | LOW | **KEEP** APPE as SSOT for portfolio policy memory |
| `decision_confidence` | **Split by layer:** committee confidence in PDC; context confidence in PCE; governor confidence in PDG | Downstream VIEWs | `tae_confidence_evolution.json` (score decay, different meaning) | **HIGH** name collision | **RENAME** in docs: profit_confidence vs signal_confidence |
| `market_session_state` | `market_session_guard.py` / bot internal | market_open_runner, dashboard | Infrastructure health (process state, not session) | MEDIUM | **KEEP** session guard; don't merge with infra health |
| `live_advisory_state` | `tae_live_advisory.json` | `live_advisory_runtime.py`, dashboard | Advisory index (upstream aggregate) | LOW | **KEEP** live_advisory.json as runtime SSOT |
| `execution_state` | `live_bot.py` + `bot_controller.py` status | dashboard, health checks | pgrep in shell scripts | LOW | **KEEP** bot_controller as ops SSOT |

---

## Detailed SSOT notes

### Accounting / PnL

**Canonical path:**

```
portfolio.csv (read-only)
    → research_core/accounting/accounting_snapshot.build_accounting_snapshot()
    → tae_accounting_snapshot.json
```

Fields: `corrected_realized_pnl`, `corrected_unrealized_pnl`, `corrected_total_trading_pnl`, `account_value_corrected`.

**Duplicate risk:** `dashboard_v2.py` recomputes open positions with its own FIFO/mark logic. `tae_decision_replay_composer.py` reads accounting snapshot but cooldown audit computes local realized legs.

**Recommendation:** Treat `tae_accounting_snapshot.json` as the **only** authoritative PnL for TAE reports. Flag any module that recomputes PnL as `diagnostic_only`.

### Portfolio positions

**Write SSOT:** `live_bot.py` → `portfolio.csv` (exclusive writer).

**Read parsers (duplicated):**

- `tae_profit_protection_shadow.py` (pandas)
- `tae_intraday_fade_intelligence.py` (pandas FIFO)
- `dashboard_v2.py` (pandas)
- `tae_portfolio_profit_governor.py` (stdlib csv)
- `tae_full_ecosystem_review.py` (stdlib csv)

**Risk:** Open share counts or avg price can diverge across parsers.

**Recommendation:** Extract one `research_core/portfolio/position_reader.py` (read-only, stdlib-first) — **do not rebuild**, **extend**.

### Profit decision stack SSOT chain

```
tae_profit_protection_shadow.json     → rules / missed USD
tae_profit_intelligence_brain.json    → PSP survival / giveback
tae_profit_memory_engine.json         → episodes / memory bias
tae_profit_decision_committee.json     → committee votes + weighted rec
tae_profit_context_engine.json         → context score + verdict
tae_profit_decision_governor.json      → reconciled ticker posture  ◄ display SSOT
tae_portfolio_profit_governor.json     → portfolio verdict           ◄ portfolio SSOT
tae_adaptive_profit_policy_engine.json → policy memory               ◄ policy SSOT
```

Each layer **owns its field**; downstream **composes**, does not re-derive upstream logic.

### Global vs profit governors

| Governor | SSOT for | Must not replace |
|----------|----------|------------------|
| `tae_decision_governor.json` | Cross-domain advisory posture (BUY universe) | Profit ticker decisions |
| `tae_profit_decision_governor.json` | Open-book profit protection posture | Live execution |

**Risk:** Operators conflate the two governors.

**Recommendation:** **KEEP_SEPARATE** with explicit naming in dashboard/CLI.

### Confidence (name collision)

| Module | Meaning |
|--------|---------|
| `tae_confidence_evolution.json` | Signal score decay / persistence hypotheses |
| PDC / PCE / PDG `confidence` | Per-ticker decision confidence |
| `tae_live_advisory.json` `confidence` | Advisory block confidence |

**Recommendation:** Prefix in docs: `signal_confidence`, `profit_decision_confidence`, `advisory_confidence`.

---

## SSOT violations to avoid in Profit Growth work

1. **Do not** create a second PnL calculator — consume `tae_accounting_snapshot.json`.
2. **Do not** create a third governor — extend PPG/APPE or global governor VIEW.
3. **Do not** duplicate PSP scoring — consume `tae_profit_intelligence_brain.json`.
4. **Do not** write `portfolio.csv` from shadow modules.
5. **Do not** wire profit policy to `live_advisory_runtime` without X.10-style evidence.

---

**READ_ONLY audit — no files modified.**
