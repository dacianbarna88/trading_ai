# TAE Dashboard Command Center — Summary

**Mode:** UI / OBSERVABILITY ONLY  
**Live trading impact:** NONE  
**Generated:** 2026-06-30

---

## Overview

`dashboard_v2.py` now includes a primary tab **🏠 TAE Command Center** that surfaces the full TAE ecosystem state from existing read-only artifacts. No changes to `live_bot.py`, BUY/SELL logic, strategy, sizing, scoring, trailing, or CSV writes.

---

## Files

| File | Role |
|------|------|
| `dashboard_v2.py` | Streamlit app — new first tab wired to command center |
| `dashboard_tae_command_center.py` | Loaders, panels, refresh button (new) |
| `TAE_DASHBOARD_COMMAND_CENTER_SUMMARY.md` | This document |

---

## Tabs (dashboard_v2.py)

| # | Tab |
|---|-----|
| 0 | **🏠 TAE Command Center** (new) |
| 1 | 📊 Dashboard |
| 2 | 📜 Alerts |
| 3 | ⚙️ Optimization |
| 4 | 🛡 Risk Manager |
| 5 | 🤖 Live Bot |
| 6 | 💰 Portfolio |
| 7 | 📈 Performance |
| 8 | 🩺 Bot Health |
| 9 | 📋 Daily Report |
| 10 | 📡 Live Signals Pro |
| 11 | 🧠 Investment Committee |
| 12 | 🧪 Strategic Validation |
| 13 | 📡 TAE Intelligence Reports |

---

## Command Center sections

1. **Metric cards** — Ecosystem verdict, bot/dashboard, market readiness, advisory, PnL, signals, X.9, SELL protection, strategies, next action  
2. **💰 Financial Performance** — corrected vs raw PnL, deposits, drag, winners/losers  
3. **📡 TAE Advisory** — action, confidence, BUY gate, warning breakdown  
4. **🧪 Shadow Validation** — X.9 events, block rate, outcome tracking  
5. **🧠 Strategy Lab** — robust/weak counts, top-N counterfactuals  
6. **🔎 Execution Integrity** — SELL mismatch audit, protection status  
7. **📚 Project Book** — sprint status from SESSION_START / PROJECT_BOOK  
8. **🔄 Refresh** — runs `bash tae_full_ecosystem_review.sh` read-only  

---

## Artifacts read (if present)

| Artifact | Use |
|----------|-----|
| `tae_full_ecosystem_review.json` | Primary aggregated source |
| `tae_live_advisory.json` | Advisory fallback / detail |
| `tae_shadow_validation_summary.json` | Shadow metrics |
| `tae_shadow_validation_events.csv` | Event table (expander) |
| `tae_portfolio_reconciliation.json` | Integrity fallback |
| `tae_execution_integrity_audit.json` | Audit fallback |
| `tae_advisory_index.json` | Status only |
| `portfolio.csv` / `live_signals.csv` | Status only (not written) |
| `PROJECT_BOOK.md` / `SESSION_START.md` | Governance panel |
| `bot_status.txt` | Bot status fallback |
| `market_session_guard.log` | Session tail (expander) |
| `live_bot.py` | Read-only SELL protection detection |

Missing or invalid files → `MISSING` / `NO_DATA`; dashboard does not crash.

---

## Layout (textual)

```
┌─────────────────────────────────────────────────────────────┐
│ 🏠 TAE Command Center                    [🔄 Run Review]      │
├─────────────────────────────────────────────────────────────┤
│ [Verdict] [Bot] [Dashboard] [Market READY]                  │
│ [Advisory] [Block BUY] [Cash] [Corrected PnL]               │
│ [Realized] [Unrealized] [STRONG BUY] [TAKE PROFIT]          │
│ [X.9] [SELL Protection] [Robust] [Weak]                     │
│ Next Action: WAIT_FOR_MARKET_OPEN…                          │
├─────────────────────────────────────────────────────────────┤
│ 💰 Financial → 📡 Advisory → 🧪 Shadow → 🧠 Strategy        │
│ → 🔎 Integrity → 📚 Project Book → Artifact status        │
└─────────────────────────────────────────────────────────────┘
```

---

## Safety

- No writes to `portfolio.csv` or `live_signals.csv`
- Refresh runs shell script only; errors shown inline
- Raw JSON hidden in expanders by default
- SELL_ADVISORY / BUY_ADVISORY labeled informational; RISK_ADVISORY labeled BUY gate

---

## Run

```bash
streamlit run dashboard_v2.py --server.port 8501
```

Optional refresh from UI or:

```bash
bash tae_full_ecosystem_review.sh
```
