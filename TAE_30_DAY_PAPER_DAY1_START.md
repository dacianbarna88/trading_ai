# TAE 30-Day PAPER Validation — Day 1 Start

**Generated:** 2026-07-08T10:22:00+00:00  
**Stack locked at:** `8e3359d538037508d6e3f381cd5398afbe1ba405`  
**Mode:** PAPER_ONLY — NO_BROKER — NO_REAL_MONEY — NO_LIVE_PROMOTION

---

## Day 1 starts with

```bash
python3 tae.py full-paper-cycle
```

Run once per trading day before market review. This executes the complete locked intelligence loop and writes all required reports.

---

## Daily rule (30-day validation freeze)

During the 30-day PAPER validation period:

1. **Do not change architecture** — no new engines, no new decision systems, no new learning systems.
2. **Only fix critical bugs** — minimal diffs, documented commits, re-run full cycle after fix.
3. **No live promotion** — `live_promotion_allowed` must remain `false`.
4. **No broker** — PAPER portfolio stays in `runtime_outputs/paper_execution/` only.
5. **No real money** — canonical portfolio files are read-only inputs.
6. **Do not modify forbidden paths:**
   - `live_bot.py`
   - `portfolio.csv`
   - `live_signals.csv`
   - `watchlist.txt`
   - `core/`
   - `research_core/`

---

## What the daily cycle produces

After `full-paper-cycle` completes, verify these outputs exist:

| Output | Purpose |
| --- | --- |
| `runtime_outputs/paper_execution/paper_portfolio.json` | Isolated PAPER portfolio SSOT |
| `runtime_outputs/paper_execution/mark_to_market.json` | Live price MTM snapshot |
| `runtime_outputs/paper_execution/rule_outcome_attribution.json` | Actual rule outcome scoring |
| `runtime_outputs/full_paper_cycle/summary.json` | Cycle summary with all key metrics |
| `TAE_FULL_PAPER_CYCLE_REPORT.md` | Human-readable daily verdict |
| `TAE_PAPER_MARK_TO_MARKET_REPORT.md` | MTM detail |
| `TAE_CANONICAL_VS_PAPER_REPORT.md` | Canonical vs PAPER comparison |
| `TAE_ADAPTIVE_WEIGHTS_REPORT.md` | Updated action weights |

---

## Day 1 baseline (closeout validation)

| Metric | Value |
| --- | ---: |
| Full cycle verdict | READY_FOR_PAPER_DAY |
| Canonical portfolio value | $30,340.91 |
| PAPER portfolio value | $30,059.46 |
| Canonical vs PAPER delta | $-281.45 |
| PAPER unrealized PnL | $-281.46 |
| MTM status | LIVE (11/11 live prices) |
| Adaptive philosophy | COLLABORATIVE |
| DPE winner | None |
| Promotion lock | PASS |
| live_promotion_allowed | false |

---

## Optional daily checks

```bash
# After full cycle — confirm forbidden paths untouched
git diff -- live_bot.py portfolio.csv live_signals.csv watchlist.txt core/ research_core/
# Expected: 0 diff

# Lightweight health (non-blocking)
python3 tae.py health
```

---

## Success criteria reference

See companion documents:

- `TAE_30_DAY_PAPER_VALIDATION_PLAN.md` — full validation plan
- `TAE_30_DAY_PAPER_SUCCESS_CRITERIA.md` — pass/fail criteria
- `TAE_30_DAY_PAPER_DAILY_CHECKLIST.md` — daily operator checklist
- `TAE_30_DAY_PAPER_DAY0_BASELINE.md` — Day 0 baseline snapshot
- `TAE_FINAL_PAPER_STACK_CLOSEOUT.md` — stack lock closeout report

---

## If something breaks

1. Record the failing step from `runtime_outputs/full_paper_cycle/summary.json` → `failed_steps`.
2. Fix only the broken component — no architecture changes.
3. Re-run `python3 tae.py full-paper-cycle`.
4. Confirm `final_verdict` returns to `READY_FOR_PAPER_DAY` or `READY_WITH_WARNINGS`.
5. Confirm forbidden diff remains 0 lines.

**Do not** enable live promotion, wire a broker, or modify canonical portfolio files to "fix" PAPER divergence.
