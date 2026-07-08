# Session Start — Trading AI / TAE

**Read this at the beginning of every working session.**

---

## Where we are

| Item | Value |
|------|--------|
| **Current approved milestone** | **Main Decision Brain Closure** — `MAIN_DECISION_BRAIN_CLOSED` |
| **Branch** | `cursor/x12b-legacy-archive-hotfix` |
| **Base commits** | `59982ee` decision state · `d39ec35` stabilization |
| **Canonical live runtime** | `live_bot.py` |
| **TAE PAPER brain** | `tae_paper_decision_engine.py` (PDE) — single final action per ticker |
| **TAE PAPER integration** | Structural governance 19-step → `full-paper-cycle` |
| **Mode** | PAPER_ONLY · ADVISORY_ONLY · NO_BROKER · NO_LIVE_PROMOTION |

---

## PAPER operator command (disciplined run)

Run **once per market session**:

```bash
cd /Users/book/Desktop/trading_ai
python3 tae.py full-paper-cycle
```

Expected verdict: `READY_FOR_PAPER_DAY` · reconciliation `PASS` · `live_promotion_allowed=false`

Audit reference: `TAE_MAIN_DECISION_BRAIN_CLOSURE_AUDIT.md` · `tae_main_decision_brain_closure_audit.json`

**Main decision brain:** PDE (`tae_paper_decision_engine.py`) produces ONE final action per ticker. Hard risk first. Decision state gates switches. Conflict resolution is evidence-only. Execution requires authorization.

**Do not** run multiple full cycles in rapid succession — high-EV tickers (AMAT/HD) may oscillate with **authorized** switches during stress testing.

---

## Current state (2026-07-08)

- **Main decision brain closed** — PDE is sole final authority; no Master Decision Authority module
- **Decision state wired** — `59982ee`: active decisions → PDE → conflict resolution → execution → memory
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

## Next allowed work

**30-day disciplined PAPER validation** — one `full-paper-cycle` per session; audit `TAE_FULL_PAPER_CYCLE_REPORT.md`

**Not allowed:** new decision engines, Master Decision Authority, live broker, live promotion unlock

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
2. **`TAE_MAIN_DECISION_BRAIN_CLOSURE_AUDIT.md`** — brain closure verdict
3. **`TAE_FINAL_PAPER_STABILIZATION_AUDIT.md`** — stabilization evidence
4. **`PROJECT_BOOK.md`** — full journal (what exists, what not to rebuild)
5. **`TAE_STRUCTURAL_GOVERNANCE.md`** — 19-step PAPER hierarchy
6. **`TAE_DECISION_STATE_REPORT.md`** — active decision state snapshot

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

*Last journal update: 2026-07-08 — Main decision brain closed (`MAIN_DECISION_BRAIN_CLOSED`)*
