# TAE Decision Replay / Protection Promotion Audit

**Generated:** 2026-07-29T14:46:56
**Verdict:** **REPLAY_VALUE_NOT_REPRODUCIBLE**

## Phase 1 — Subsystem audit

- Replay costly decisions: **0**
- Protection validation observations: **None**
- Best strategy: **None**
- Gates passed: **None**
- Claimed protection Δ vs HOLD: **$None**

## Phase 2 — Value claim reproduction

- Claimed formula: `sum(shadow_trailing_1) - sum(hold_pnl) over fade observations in tae_intraday_fade_history.csv`
- Claimed shadow delta: **$0.00**
- PAPER-linked fade recalc: **$2096.41** (170 obs)
- Reproduced on clean PAPER history: **False**
- Invalidation: Claimed $0.00 is fade-history shadow simulation (None obs); clean PAPER-linked fade recalc=$2096.41 (170 obs, 25 tickers)

## Phase 3 — Allowed influence

- HOLD scoring adjustment on held winners with fade/missed-profit evidence
- PROTECT_PAPER urgency boost from top_costly_decisions + MISSED_PROFIT_PROTECTION
- REDUCE_PAPER partial exit bias from shadow trailing recommendation
- exit urgency via failure_mode severity (HIGH → stronger PROTECT/REDUCE)
- confidence adjustment via existing named rules (MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW)

## Phase 4 — Baseline vs challenger

| Metric | Baseline | Challenger |
|--------|----------|------------|
| Profit vs $30k | $-82.74 | $-82.74 |
| Max drawdown % | 1.40 | 1.40 |
| Profit factor | 0.11 | 0.11 |
| Avg winner | $10.90 | $10.90 |
| Avg loser | $-52.03 | $-52.03 |
| Exit quality index | 32.38 | 32.38 |
| Tickers improved | — | 0 |

## Phase 5 — Promotion checks

- higher_profit: **False**
- drawdown_equal_or_lower: **True**
- integrity_ok: **True**
- reconciliation_ok: **True**
- no_churn_regression: **True**
- no_hard_risk_regression: **True**
- two_tickers_improved: **False**
- multiple_clean_outcomes: **True**
- replay_value_reproducible: **False**
- protection_gates_passed: **False**
- promotion_readiness_not_blocked: **True**

