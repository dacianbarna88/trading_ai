# TAE Sprint X.8 — Live Bot Advisory Integration Summary

**Date:** 2026-06-29  
**Mode:** CONTROLLED_INTEGRATION | ADVISORY_RISK_FILTER_ONLY  
**Live trading impact:** TAE blocks **new BUY only** on `RISK_ADVISORY` — never forces BUY/SELL

---

## Objective

Integrate `tae_live_advisory.json` into `live_bot.py` as a **read-only risk filter** at the start of each signal cycle.

---

## Deliverables

| Artifact | Role |
|----------|------|
| `research_core/governance/live_advisory_runtime.py` | Runtime loader + `should_block_new_buy()` |
| `live_bot.py` | Minimal integration in `generate_signals()` / `manage_portfolio()` |
| `TAE_X8_LIVE_BOT_ADVISORY_INTEGRATION_SUMMARY.md` | This document |

---

## New runtime API

| Function | Purpose |
|----------|---------|
| `load_live_advisory()` | Parse `tae_live_advisory.json`; SAFE fallback on missing/invalid/stale |
| `get_advisory_action()` | Normalized action string |
| `should_block_new_buy()` | **True** only for `RISK_ADVISORY` (valid file) or `stale_block_buy=true` |
| `advisory_runtime_summary()` | One-line log summary |

Self-check: `python3 research_core/governance/live_advisory_runtime.py`

---

## `live_bot.py` modifications

### Zone 1 — `generate_signals()` (~lines 557–560)

- Loads advisory once per cycle via `load_live_advisory()`
- Passes `advisory_state` into `manage_portfolio()`

### Zone 2 — `manage_portfolio()` signature + TAE preamble (~lines 458–482)

- Optional `advisory_state` parameter
- Logs `advisory_runtime_summary()`
- Logs warnings, `BUY_ADVISORY` supportive message, `SELL_ADVISORY` informational message
- Computes `block_new_buy` / `tae_block_reason`

### Zone 3 — BUY gate only (~lines 504–523)

- Before existing BUY conditions: if `block_new_buy` → log and **skip** `buy_position()`
- If `BUY_ADVISORY` and BUY proceeds → extra log `"TAE advisory supportive pentru {ticker}"`
- **SELL branch untouched** (lines 536–551)

### Not modified

- `buy_position()` / `sell_position()` implementations
- Scoring, regime filter, session gate, watchlist logic
- SELL / STOP / TAKE PROFIT conditions

---

## Behavior by advisory action

| Action | BUY | SELL / STOP / TAKE PROFIT |
|--------|-----|---------------------------|
| **NO_ACTION** | Unchanged (existing rules) | Unchanged |
| **RISK_ADVISORY** | **New BUY blocked** + log reason | **Allowed** (unchanged) |
| **BUY_ADVISORY** | **No auto-buy**; supportive log only if BUY would execute | Unchanged |
| **SELL_ADVISORY** | Unchanged | **No auto-sell**; informational log only |
| **missing / invalid / stale** | Unchanged unless `stale_block_buy=true` in JSON | **Never blocked** by TAE |
| **missing + stale_block_buy=true** | New BUY blocked | SELL unchanged |

Stale threshold: `TAE_ADVISORY_MAX_AGE_HOURS` env (default **24h**).

---

## Safety guarantees

- TAE **cannot force BUY** — no code path calls `buy_position()` based on `BUY_ADVISORY` alone
- TAE **cannot force SELL** — `SELL_ADVISORY` is log-only
- TAE **blocks new BUY** only via `should_block_new_buy()` → `RISK_ADVISORY` or explicit `stale_block_buy=true`
- `buy_position()` / `sell_position()` never read TAE JSON directly

---

## Validation

| Check | Result |
|-------|--------|
| `python3 -m py_compile live_bot.py` | PASS |
| `python3 -m py_compile research_core/governance/live_advisory_runtime.py` | PASS |
| `python3 research_core/governance/live_advisory_runtime.py` | SELF_CHECK PASS |
| Current advisory sample | `RISK_ADVISORY` → `block_new_buy=True` |
| TAE executes BUY/SELL directly | **No** |

---

## Git status

```
M live_bot.py
?? research_core/governance/live_advisory_runtime.py
?? TAE_X8_LIVE_BOT_ADVISORY_INTEGRATION_SUMMARY.md
```

Regenerate advisory before live cycles:

```bash
python3 tae_live_advisory_demo.py
```

---

*End of X.8 summary.*
