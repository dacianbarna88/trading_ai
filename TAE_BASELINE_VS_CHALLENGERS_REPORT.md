# TAE Baseline vs Challengers Report

**Generated:** 2026-07-14

## Baseline (PAPER SSOT)

- profit vs $30,000 base: **$-185.30**
- realized: **$-451.60** · unrealized: **$-74.62**
- profit factor: **0.0** · win rate: **0.0%**
- max drawdown: **1.7344%**
- closed outcomes: **4**

## Challengers

### C1 — reduce_high_risk_skip_penalty [REJECT]
- Parameter: HIGH_RISK SKIP_PAPER score boost `15.0` → `8.0`
- Simulated profit vs base: **$-200.30** (Δ -15.00)
- Reject reasons: does_not_beat_baseline_pnl, single_ticker_or_none, single_session_only, insufficient_closed_outcomes, negative_expectancy_risk

### C2 — stronger_buy_after_hard_risk [REJECT]
- Parameter: Block BUY_PAPER within 24h of HARD_RISK SELL on same ticker `none` → `cooldown_after_hard_risk_sell=24h`
- Simulated profit vs base: **$-162.31** (Δ +22.99)
- Reject reasons: single_ticker_or_none, single_session_only, insufficient_closed_outcomes

### C3 — reject_hold_to_protect [REJECT]
- Parameter: REJECT validation on HOLD → bias PROTECT_PAPER trim `HOLD maintained` → `10% urgency trim on REJECT+loss>1%`
- Simulated profit vs base: **$-179.30** (Δ +6.00)
- Reject reasons: single_ticker_or_none, single_session_only, insufficient_closed_outcomes

### C4 — increase_collaborative_protect_bias [REJECT]
- Parameter: COLLABORATIVE PROTECT/HOLD score bias `+5/+3` → `+8/+5`
- Simulated profit vs base: **$-175.30** (Δ +10.00)
- Reject reasons: single_session_only, insufficient_closed_outcomes

### C5 — loss_position_reduce_bias [REJECT]
- Parameter: Open position current_pct < -1.5% → REDUCE_PAPER +12 `0.0` → `12.0`
- Simulated profit vs base: **$-173.30** (Δ +12.00)
- Reject reasons: single_session_only, insufficient_closed_outcomes

