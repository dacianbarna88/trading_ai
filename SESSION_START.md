# Session Start — Trading AI / TAE

**Read this at the beginning of every working session.**

---

## Where we are

| Item | Value |
|------|--------|
| **Current approved milestone** | **PAPER Stabilization** — decision state wiring `59982ee` + final audit |
| **Last completed sprint line** | Decision state anti-churn wiring + stabilization validation (2026-07-08) |
| **Canonical live runtime** | `live_bot.py` |
| **TAE live integration** | X.8 advisory **risk gate** + X.9 **BUY observability ledger** |
| **TAE PAPER integration** | Structural governance 19-step hierarchy → `full-paper-cycle` |
| **TAE shadow integration** | Market-open intelligence runner → decision governor VIEW (no live execution) |
| **Mode** | PAPER_ONLY · ADVISORY_ONLY · NO_BROKER · NO_LIVE_PROMOTION |

---

## PAPER operator command (disciplined run)

Run **once per market session**:

```bash
cd /Users/book/Desktop/trading_ai
python3 tae.py full-paper-cycle
```

Expected verdict: `READY_FOR_PAPER_DAY` · reconciliation `PASS` · `live_promotion_allowed=false`

Audit reference: `TAE_FINAL_PAPER_STABILIZATION_AUDIT.md` · `tae_final_paper_stabilization_audit.json`

**Do not** run multiple full cycles in rapid succession — high-EV tickers (AMAT/HD) may oscillate with **authorized** switches during stress testing.

---

## Current state (2026-07-08)

- **Decision state wired** — `59982ee`: active decisions → PDE → conflict resolution → execution → longitudinal memory
- **Anti-churn gates active** — unauthorized BUY→SELL blocked (AIR.PA/DIA/GE → HOLD + `SKIPPED_SWITCH_NOT_AUTHORIZED`)
- **STOP_REENTRY_CHURN enforced** — 30m cooldown after SELL; strong EV bypass only
- **Hard -3% SELL bypass** — AMAT hard stop SELL when breach active
- **X.8 risk gate connected** — `live_bot.py` reads `tae_live_advisory.json`; `RISK_ADVISORY` blocks **new BUY only**
- **X.9 shadow validation ledger connected** — BUY path logs to `tae_shadow_validation_events.csv`
- **Governor live blocking** — **NOT wired** (by design)
- **Live promotion** — **LOCKED false** (`tae_live_promotion_lock.py`)

---

## What is already done (do not repeat)

- Full TAE ecosystem pipeline (orchestrator, evidence, evolution, ranking, registry, gates)
- **Structural governance** — `tae_structural_governance.py` single PAPER hierarchy
- **Decision state builder** — `tae_decision_state.py` (not a decision engine)
- **Conflict resolution EV evidence** — `tae_conflict_resolution.py`
- **PAPER decision engine + execution** — isolated portfolio under `runtime_outputs/paper_execution/`
- Phase X: discovery, simulation, historical execution/analysis, meta intelligence
- Dashboard TAE Intelligence Reports + Advisory Index (X.7A/B)
- **Live bot reads advisory** — `RISK_ADVISORY` blocks **new BUY only** (X.8)
- **Shadow validation ledger** — structured BUY evaluation events (X.9)
- Decision replay composer, knowledge base VIEW, decision governor VIEW

---

## What we do NOT have (do not assume)

- TAE forcing BUY or SELL on **live** portfolio
- TAE changing live sizing, scores, trailing stop, or `config/settings.py`
- Decision governor controlling live blocking
- **Live promotion** — always false until explicit architect unlock
- Master Decision Authority module (explicitly rejected)
- Automatic commit/push in checkpoint script

---

## What is connected vs report-only

| Connected to PAPER cycle | Report-only / shadow |
|--------------------------|----------------------|
| `tae.py full-paper-cycle` → structural governance | Decision governor VIEW |
| PDE → conflict resolution → decision state → execution | Knowledge base VIEW |
| Longitudinal outcome memory | Meta evolution recommendations |
| DPE competitive/collaborative (isolated) | Ranking → live watchlist |
| Investment Council synthesis | Canonical vs paper delta (report) |
| Promotion lock (hard false) | |

**Legacy / not canonical:** `live_bot_v5_1.py`, `telegram_bot.py`, `signal_to_decision_engine.py`

---

## Next allowed sprint

**Disciplined 30-day PAPER validation** — daily `full-paper-cycle`, track `TAE_FULL_PAPER_CYCLE_REPORT.md`

Do **not** wire governor to live blocking or enable live promotion without explicit architect approval.

---

## Quick state check (run first)

```bash
cd /Users/book/Desktop/trading_ai

python3 tae.py full-paper-cycle    # expect READY_FOR_PAPER_DAY
git diff -- live_bot.py portfolio.csv live_signals.csv watchlist.txt core/ research_core/  # expect empty
python3 tae_quick_health_check.py
```

---

## Canonical docs

1. **`SESSION_START.md`** — this file
2. **`TAE_FINAL_PAPER_STABILIZATION_AUDIT.md`** — PAPER stabilization verdict
3. **`PROJECT_BOOK.md`** — full journal (what exists, what not to rebuild)
4. **`TAE_STRUCTURAL_GOVERNANCE.md`** — 19-step PAPER hierarchy
5. **`TAE_DECISION_STATE_REPORT.md`** — active decision state snapshot

---

## Before writing new code

1. Open `PROJECT_BOOK.md` §11 — **What Must NOT Be Rebuilt**
2. **NO_NEW_MODULES** — extend existing files only
3. Confirm sprint mode: PAPER_ONLY · ADVISORY_ONLY
4. Do **not** modify `live_bot.py` / `portfolio.csv` / `core/` without explicit sprint

---

## End of session

```bash
bash tae_checkpoint.sh
# Update PROJECT_BOOK.md §1 / §12 / sprint history
# Regenerate TAE_MASTER_CONTEXT.md if canonical docs changed
# git add … && git commit && git push  (manual)
```

---

*Last journal update: 2026-07-08 — PAPER stabilization audit (`READY_FOR_DISCIPLINED_PAPER_RUN`)*
