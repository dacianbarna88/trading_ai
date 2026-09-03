# Session Start — Trading AI / TAE

**Read this at the beginning of every working session.**  
**Constitution SSOT:** [`TAE_CONSTITUTION.md`](TAE_CONSTITUTION.md) **v2.2**  
**Journal:** [`PROJECT_BOOK.md`](PROJECT_BOOK.md)

On conflict: **Constitution wins.**

---

## 1. Project state (2026-08-03)

| Item | Value |
|------|--------|
| Infrastructure | **CLOSED** |
| Canonical FPC | **ACTIVE** |
| V1 | **ACTIVE** (benchmark PAPER book) |
| V2 | **ACTIVE** (challenger PAPER book, same FPC) |
| Dual strategy | **`V1_V2_DUAL_STRATEGY_ACTIVE`** |
| Decision Brain | **ACTIVE** (PDE `action`) |
| Binding SKIP gate | **ACTIVE in PAPER** — provisional; forward cohort decides permanence |
| Forward cohort | **ACTIVE** |
| Learning | **ACTIVE** (isolated by `strategy_id`) |
| Hard Risk | **PROTECTED** |
| SELL | **PROTECTED** |
| Broker | **OFF** |
| Live promotion | **Blocked** |
| Documentation | **CLOSED** (`TAE_CANONICAL_DOCUMENTATION_CLOSED`) |
| Architecture | **`ARCHITECTURE_FREEZE`** |

**Roadmap phase:** **FAZA II — Economic Validation** (FAZA I done; FAZA III not started; FAZA IV LIVE forbidden until proof + Owner approval).

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
Do **not** start FAZA III/IV or V3 without Owner direction.

---

## 9. End of session

```bash
bash tae_checkpoint.sh
# If docs changed: ensure Constitution / Book / Session still agree
# git add … && git commit  — only if Owner requested
```

---

*Session Start — synced to Constitution v2.2 · ARCHITECTURE_FREEZE · 2026-08-03*
