# Session Start — Trading AI / TAE

**Read this at the beginning of every working session — this file is the single entry point for the project.**
**Constitution SSOT:** [`TAE_CONSTITUTION.md`](_archive_unused_reports_20260817/TAE_CONSTITUTION.md) **v2.2** — ⚠️ archived 2026-08-17, no longer at repo root. Treat as historical background on architecture/governance intent; this file + `PROJECT_BOOK.md` are the current state of record until/unless the Owner restores or replaces it.
**Journal:** [`PROJECT_BOOK.md`](PROJECT_BOOK.md)
**Document index (everything else lives where):** [§10 below](#10-document-index--where-everything-lives)

On conflict: **Constitution (historical intent) → this file (current state) → PROJECT_BOOK (architecture detail).**

---

## 1. Project state (2026-09-21)

| Item | Value |
|------|--------|
| Infrastructure | **CLOSED** |
| Canonical FPC | **ACTIVE** |
| V1 | **ACTIVE** (benchmark PAPER book) |
| V2 | **ACTIVE** (challenger PAPER book, same FPC) |
| V3 / V_learning | **ACTIVE in PAPER** (adaptive/profit-only strategy, isolated cash+journal; not yet compared conclusively vs V1/V2 — see [[project_v_learning_initiative]] in Claude memory) |
| exp_mean_reversion | **ACTIVE in PAPER** (orthogonal statistical-oversold arm, added 2026-09-12, 0% signal overlap with V1/V2/V3) |
| exp_quality_longterm | **ACTIVE in PAPER** (F-Score long-horizon arm, monthly rebalance, added 2026-09-14) |
| exp_short_margin | **PAUSED** on new entries (poor PF, cross-arm collision guard added) |
| Dual strategy | **`V1_V2_DUAL_STRATEGY_ACTIVE`** |
| Decision Brain | **ACTIVE** (PDE `action`) |
| Binding SKIP gate | **ACTIVE in PAPER** — provisional; forward cohort decides permanence |
| Forward cohort | **ACTIVE** |
| Learning | **ACTIVE** (isolated by `strategy_id`) |
| Entry-signal quality sprint | **DONE** — score gate fixed (60→100, "STRONG BUY" bypass removed), VIX+liquidity compound gate wired across V1/V2/V3/mean-reversion, journal-reparse perf bug class eliminated systemically (see `feedback_verify_perf_fixes_all_call_sites` in Claude memory) |
| 7-item profit roadmap (2026-09-14) | **7/7 resolved** — done, rejected (with data), or explicitly time-gated; see [[project_entry_signal_quality_sprint]] |
| Hard Risk | **PROTECTED** |
| SELL | **PROTECTED** |
| Broker | **OFF** |
| Live promotion | **Blocked** |
| Documentation | **CLOSED** (`TAE_CANONICAL_DOCUMENTATION_CLOSED`) — plus stale as of this edit; see §10 |
| Architecture | **`ARCHITECTURE_FREEZE`** |

**Roadmap phase:** **FAZA II — Economic Validation** (FAZA I done; FAZA III not started; FAZA IV LIVE forbidden until proof + Owner approval).

Everything above stays **PAPER_ONLY / NO_BROKER / NO_LIVE_EXECUTION**. Nothing in this project has ever placed a real trade.

---

## 2. Mandatory rules

1. Constitution is the sole documentary SSOT for project state.  
2. PAPER only for economic work; broker OFF; no auto LIVE promote.  
3. Do not restore parallel-paper daemon or retired LaunchAgents.  
4. V1 and V2 books stay separate — no cross cash/portfolio mutation.  
5. Hard Risk and SELL semantics are protected unless an explicit Owner sprint says otherwise.  
6. Binding SKIP gate is **provisional** — do not declare it permanent without mature cohort outcomes.  
7. Prove before patch; measure forward; do not invent fills.  
8. Commit only when the Human Owner asks.  
9. **ARCHITECTURE_FREEZE** — no structural change without economic audit + statistical proof + explicit Owner approval. Without all three: only bug fix, maintenance, compatibility, documentation.

---

## 3. What you must NOT do

- Modify BUY / SELL / Hard Risk / Learning / V1 / V2 **unless the sprint explicitly authorizes it**  
- Create V3 or a second FPC / accounting engine  
- Hard-gate PPG PROTECT, 7D NEGATIVE, or score 100 without new global proof  
- Treat SKIP gate as permanent constitutional dogma  
- Restore daemon / LaunchAgent / orphan cron for retired arms  
- Touch LIVE `core/trailing.py` for V2 experiments  
- Skip audit when changing economic behavior  
- Force-push; commit secrets; commit without Owner request  
- Structural architecture changes under freeze without the triad (audit + proof + Owner)  

---

## 4. Audit order (before any change)

1. Read **this file** + **Constitution** § relevant sections  
2. Read **PROJECT_BOOK** for architecture pointers  
3. Grep existing modules — do not rebuild  
4. Confirm sprint mode: `AUDIT` / `REPORT_ONLY` / `PAPER_PATCH` / `DOCS_ONLY`  
5. List protected surfaces: SELL, Hard Risk, LIVE, broker, V1/V2 isolation  
6. Define verification: tests, FPC/health as required, no invented journals  

---

## 5. Working mode

```
Think → Design → Check existing → Minimal change → Verify → Measure → (Commit if Owner asks)
```

| Mode | Allowed |
|------|---------|
| DOCS_ONLY | Markdown/JSON reports only |
| AUDIT / REPORT_ONLY | Read-only analysis + deliverables |
| BUGFIX / MAINTENANCE / COMPAT | Allowed under ARCHITECTURE_FREEZE |
| PAPER_PATCH (structural) | **Frozen** unless triad satisfied |
| LIVE | Forbidden unless Owner + Constitution FAZA IV criteria |

---

## 6. Canonical commands

```bash
cd /Users/book/Desktop/trading_ai

# Health
python3 tae.py health

# Full PAPER cycle (V1 + V2 dual)
python3 tae.py full-paper-cycle

# Mark-to-market (V1 book)
python3 tae.py paper-mark-to-market

# Hermetic unit suite
python3 tae.py test

# Checkpoint (when ending a sprint)
bash tae_checkpoint.sh
```

SKIP gate rollback (PAPER only): `DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED=false`

---

## 7. SSOT documents

| Priority | Document | Role |
|----------|----------|------|
| 1 | `TAE_CONSTITUTION.md` | Project-state constitution |
| 2 | `SESSION_START.md` | This bootstrap |
| 3 | `PROJECT_BOOK.md` | Architecture journal |
| 4 | `TAE_DEVELOPMENT_PROTOCOL.md` | Development process |
| 5 | `TAE_GIT_GOVERNANCE.md` | Git rules |

Sprint verdicts (`TAE_BINDING_DECISION_BRAIN_SKIP_PAPER_GATE.md`, dual activation, infra closure, …) are history — use them for facts, not as competing constitutions.

---

## 8. Next default work

`ACCUMULATE_NATURAL_BINDING_SKIP_GATE_OUTCOMES` — mature forward cohort; then decide keep / soft / rollback.
`ACCUMULATE_POST_FIX_DATA` — entry-signal-quality sprint fixes landed 2026-09-12/16; let 1-2+ weeks of fresh data accumulate before re-evaluating arm performance (pre-fix data is stale/misleading for that comparison).
V3/V_learning vs V1/V2 economic comparison — not yet conclusive; do not connect any strategy to a live broker until that comparison is done and the Owner approves.
Do **not** start FAZA III/IV without Owner direction. V3 already exists (approved 2026-08, see §1) — the old "do not create V3" rule in `PROJECT_BOOK.md` §14 predates that approval and is superseded here.

---

## 9. End of session

```bash
bash tae_checkpoint.sh
# If docs changed: ensure Constitution / Book / Session still agree
# git add … && git commit  — only if Owner requested
```

---

## 10. Document index — where everything lives

This repo has 100+ report/status `.md` files at the root. Rather than merging them (lossy, unreadable), here's the map. **Start with this file — everything else is reference, not a competing entry point.**

| Category | Where | Notes |
|---|---|---|
| **Governance / SSOT** | `SESSION_START.md` (this file), `PROJECT_BOOK.md`, `TAE_DEVELOPMENT_PROTOCOL.md`, `TAE_GIT_GOVERNANCE.md` | The only docs meant to be authoritative for current state/process |
| **Constitution (historical)** | `_archive_unused_reports_20260817/TAE_CONSTITUTION.md` + `..._AUDIT.md` + `..._RECOVERY_REPORT.md` | Archived 2026-08-17; v2.2 architecture/rules intent, not live status |
| **Auto-generated rolling reports** | `TAE_*_REPORT.md` (e.g. `TAE_ADAPTIVE_WEIGHTS_REPORT.md`, `TAE_DECISION_STATE_REPORT.md`, `TAE_PAPER_*_REPORT.md`) | Regenerated by scheduled jobs each cycle — read the latest, don't diff them for "changes," they're snapshots not prose |
| **Sprint / audit history** | `TAE_*_AUDIT.md`, `TAE_*_SUMMARY.md`, `TAE_X7*`/`X8*`/`X9*` files, `cleanup_*.md` | Point-in-time facts about a completed sprint — never edit retroactively, treat like commit messages |
| **V_learning (V3) design & profit-engine research** | `tae_profit_*.md`, `tae_adaptive_profit_policy_engine.md`, `tae_growth_intelligence.md`, `tae_decision_event_bus.md`, `tae_execution_splitter.md`, `TAE_DPE*_REPORT.md`, `TAE_LEARNING_*.md`, `TAE_LONG*_REPORT.md` | Mostly research/speculation docs from the V3 build — check `git log`/actual code before trusting one as "implemented" |
| **Operational runbooks** | `tae_startup_verify.md`, `tae_scanner_refresh.md`, `tae_promotion_queue.md`, `tae_candidate_queue.md`, `tae_watchlist_proposal.md`, `market_session_guard_plan.md` | Small ops notes, not governance |
| **Claude's memory of this project** (cross-session context, decisions, "why") | `/Users/book/.claude/projects/-Users-book-trading-ai-restored/memory/` (`MEMORY.md` index + topic files) | Not part of this git repo — lives alongside Claude Code's session data. This is where "what we agreed and why" across conversations is tracked; it complements, not duplicates, the docs above. |
| **Backups / archives (outside this repo)** | `~/TradingAI_Cloud_Backup/`, `~/trading_ai_backups/`, Desktop `.zip`s | Point-in-time snapshots of the whole repo, not working docs — don't read these for current state |

**Rule of thumb:** if a doc's claim conflicts with this file, this file wins for "what's active now"; `PROJECT_BOOK.md` wins for "why/architecture"; the archived Constitution wins for "original design intent" only where neither of the above has since superseded it (as with V3 above).

---

*Session Start — synced to `PROJECT_BOOK.md` · ARCHITECTURE_FREEZE · 2026-09-21*
