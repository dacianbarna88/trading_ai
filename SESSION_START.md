# Session Start — Trading AI / TAE

**Read this at the beginning of every working session.**

---

## Where we are

| Item | Value |
|------|--------|
| **Latest sprint** | **X.8** — Live Bot Advisory Integration |
| **Canonical live runtime** | `live_bot.py` |
| **TAE live integration** | Advisory **risk gate only** via `tae_live_advisory.json` |
| **Mode** | PAPER_ONLY · NO_BROKER · NO_AUTO_EXECUTION |

---

## What is already done (do not repeat)

- Full TAE ecosystem pipeline (orchestrator, evidence, evolution, ranking, registry, gates)
- Phase X: discovery, simulation, historical execution/analysis, meta intelligence
- Event memory **scaffold** (0 events) — not ingestion
- Dashboard TAE Intelligence Reports + Advisory Index (X.7A/B)
- `tae_advisory_index.json` aggregator (X.7B)
- `tae_live_advisory.json` bridge (X.7C)
- **Live bot reads advisory** — `RISK_ADVISORY` blocks **new BUY only** (X.8)
- Connectivity audits X.7 + indirect audit X.7 fix

---

## What we do NOT have (do not assume)

- TAE forcing BUY or SELL
- TAE changing sizing, scores, trailing stop, or `config/settings.py`
- Event memory ingestion / live news models
- Shadow validation stats for blocked BUYs (planned X.9)
- Automatic commit/push in checkpoint script

---

## What is connected vs report-only

| Connected to LIVE | Report-only |
|-------------------|-------------|
| `live_bot.py` → CSV writes | All other `tae_*.json` |
| `live_bot.py` → `tae_live_advisory.json` (BUY gate) | Meta evolution recommendations |
| Dashboard → display + start/stop bot | Ranking → live watchlist |
| TAE read-only → `portfolio.csv`, `live_signals.csv` | Implementation patches |

**Legacy / not canonical:** `live_bot_v5_1.py`, `telegram_bot.py`, `signal_to_decision_engine.py`, `daily_intelligence_runner.py`

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
cat bot_status.txt 2>/dev/null || echo "bot_status missing"
python3 -c "import json; d=json.load(open('tae_live_advisory.json')); print(d['advisory']['action'])"
```

---

## Canonical docs

1. **`PROJECT_BOOK.md`** — full journal (what exists, what not to rebuild)
2. **`TAE_DEVELOPMENT_PROTOCOL.md`** — rules of engagement
3. Latest sprint summary: **`TAE_X8_LIVE_BOT_ADVISORY_INTEGRATION_SUMMARY.md`**

---

## Before writing new code

1. Open `PROJECT_BOOK.md` §11 — **What Must NOT Be Rebuilt**
2. Grep `research_core/` for existing module
3. Confirm sprint mode: AUDIT / REPORT_ONLY / CONTROLLED_INTEGRATION
4. Do **not** modify `live_bot.py` trading logic unless sprint explicitly says so

---

## End of session

```bash
bash tae_checkpoint.sh
# Update PROJECT_BOOK.md §1 / §12 / sprint history
# git add … && git commit && git push  (manual)
```

---

*Last governance reset: 2026-06-29 — see `TAE_GOVERNANCE_RESET_SUMMARY.md`*
