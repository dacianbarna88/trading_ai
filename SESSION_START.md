# Session Start — Trading AI / TAE

**Read this at the beginning of every working session.**

---

## Where we are

| Item | Value |
|------|--------|
| **Last completed sprint** | **X.9** — Connected Shadow Validation Runtime Ledger |
| **Canonical live runtime** | `live_bot.py` |
| **TAE live integration** | X.8 advisory **risk gate** + X.9 **BUY observability ledger** |
| **Mode** | PAPER_ONLY · NO_BROKER · NO_AUTO_EXECUTION |

---

## Current state (2026-06-29)

- **X.8 risk gate connected** — `live_bot.py` reads `tae_live_advisory.json`; `RISK_ADVISORY` blocks **new BUY only**
- **X.9 shadow validation ledger connected** — BUY path logs to `tae_shadow_validation_events.csv` via `shadow_validation_ledger.py`
- **BUY path observability active** — event types: `BUY_ALLOWED`, `BUY_BLOCKED_BY_TAE`, `BUY_SKIPPED_OTHER_REASON`
- **SELL logic untouched** — STOP / TAKE PROFIT / SELL branch not modified by X.8 or X.9
- **Outcome tracking** — `PENDING_NEXT_PHASE` (no forward PnL on blocked BUYs yet)

---

## What is already done (do not repeat)

- Full TAE ecosystem pipeline (orchestrator, evidence, evolution, ranking, registry, gates)
- Phase X: discovery, simulation, historical execution/analysis, meta intelligence
- Event memory **scaffold** (0 events) — not ingestion
- Dashboard TAE Intelligence Reports + Advisory Index (X.7A/B)
- `tae_advisory_index.json` aggregator (X.7B)
- `tae_live_advisory.json` bridge (X.7C)
- **Live bot reads advisory** — `RISK_ADVISORY` blocks **new BUY only** (X.8)
- **Shadow validation ledger** — structured BUY evaluation events (X.9)
- Connectivity audits X.7 + indirect audit X.7 fix

---

## What we do NOT have (do not assume)

- TAE forcing BUY or SELL
- TAE changing sizing, scores, trailing stop, or `config/settings.py`
- Event memory ingestion / live news models
- **Outcome attribution** for blocked BUYs (planned X.10 — after ledger accumulates events)
- Automatic commit/push in checkpoint script

---

## What is connected vs report-only

| Connected to LIVE | Report-only |
|-------------------|-------------|
| `live_bot.py` → CSV writes | All other `tae_*.json` |
| `live_bot.py` → `tae_live_advisory.json` (BUY gate) | Meta evolution recommendations |
| `live_bot.py` → `tae_shadow_validation_events.csv` (BUY log) | Ranking → live watchlist |
| `tae_shadow_validation_report.py` → summary JSON | Implementation patches |
| Dashboard → display + start/stop bot | |
| TAE read-only → `portfolio.csv`, `live_signals.csv` | |

**Legacy / not canonical:** `live_bot_v5_1.py`, `telegram_bot.py`, `signal_to_decision_engine.py`, `daily_intelligence_runner.py`

---

## Next allowed sprint

**X.10 — Outcome Tracking / Attribution for Blocked BUYs**

Start only after `tae_shadow_validation_events.csv` has accumulated real events from live bot cycles.

---

## Quick state check (run first)

```bash
cd /Users/book/Desktop/trading_ai

# Full checkpoint (recommended)
bash tae_checkpoint.sh

# Or minimal
git status
python3 tae_quick_health_check.py
python3 tae_live_advisory_demo.py
python3 tae_shadow_validation_report.py
cat bot_status.txt 2>/dev/null || echo "bot_status missing"
python3 -c "import json; d=json.load(open('tae_live_advisory.json')); print(d['advisory']['action'])"
```

---

## Canonical docs

1. **`PROJECT_BOOK.md`** — full journal (what exists, what not to rebuild)
2. **`TAE_DEVELOPMENT_PROTOCOL.md`** — rules of engagement
3. Latest sprint summary: **`TAE_X9_SHADOW_VALIDATION_SUMMARY.md`**

---

## Before writing new code

1. Open `PROJECT_BOOK.md` §11 — **What Must NOT Be Rebuilt**
2. Grep `research_core/` for existing module
3. Confirm sprint mode: AUDIT / REPORT_ONLY / CONTROLLED_INTEGRATION / CONNECTED_OBSERVABILITY
4. Do **not** modify `live_bot.py` trading logic unless sprint explicitly says so

---

## End of session

```bash
bash tae_checkpoint.sh
# Update PROJECT_BOOK.md §1 / §12 / sprint history
# git add … && git commit && git push  (manual)
```

---

*Last journal update: 2026-06-29 — Sprint X.9 closed*
