# TAE Profit Pipeline Report

**Generated:** 2026-07-13T23:56:57+00:00
**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_PORTFOLIO_MUTATION
**Decision cycle:** 2026-07-13T23:54:32+00:00

## Pipeline summary

- Opportunities detected: **25**
- Signals generated: **25**
- Final decisions: **25** (BUY 1 / SELL 0 / HOLD 6 / SKIP 13 / PROTECT 5)
- Actionable decisions: **6**
- Orders created: **0**
- Orders executed: **0**
- Orders blocked/skipped: **12**
- Trades written: **0**
- Realized PnL: **$-451.60**
- Unrealized PnL: **$-74.62**
- PAPER account value: **$29,814.70**
- Profit vs validation capital base ($30,000.00): **$-185.30**

## Conversion metrics

- opportunity_to_signal: **16/25** (64.0%)
- signal_to_actionable_decision: **6/25** (24.0%)
- actionable_decision_to_order: **0/6** (0.0%)
- order_to_execution: **0/0** (0.0%)
- execution_to_profitable_outcome: **0/0** (0.0%)

## Block reason rollup

- same_action: **6**
- cooldown_reentry_churn: **2**
- policy_skip: **13**
- other: **4**

## Profit attribution

- Profitable decisions: **3**
- Losing decisions: **8**
- Blocked avoided loss (heuristic): **0**
- Blocked missed profit (heuristic): **9**
- Unresolved outcomes: **16**

## Data quality

- decision_id join coverage: **0/25** (0.0%)
- low-confidence joins: **6**
- profit integrity: **PAPER_PROFIT_INTEGRITY_CLOSED** (ok=True)
- reconciliation: **PASS**
- stale/fallback marks: **11**

## Per-ticker timeline (current cycle)

- **HD** [PDEC-HD-0010] signal=STRONG BUY → BUY_PAPER → skipped_same_action (same_action) → PnL $0.00 / val=NEEDS_MORE_DATA
- **HSBA.L** [PDEC-HSBA.L-0011] signal=WAIT → PROTECT_PAPER → skipped_same_action (same_action) → PnL $-9.27 / val=PROMISING
- **QQQ** [PDEC-QQQ-0020] signal=WAIT → PROTECT_PAPER → skipped_same_action (same_action) → PnL $-5.41 / val=NEEDS_MORE_DATA
- **AAPL** [PDEC-AAPL-0001] signal=STRONG BUY → PROTECT_PAPER → skipped_same_action (same_action) → PnL $35.24 / val=CONTINUE_TESTING
- **GE** [PDEC-GE-0009] signal=STRONG BUY → PROTECT_PAPER → skipped_same_action (same_action) → PnL $-7.24 / val=CONTINUE_TESTING
- **LLY** [PDEC-LLY-0012] signal=STRONG BUY → PROTECT_PAPER → skipped_same_action (same_action) → PnL $-35.12 / val=NEEDS_MORE_DATA
- **MRK** [PDEC-MRK-0014] signal=STRONG BUY → HOLD_PAPER → MISSING (other) → PnL $-39.15 / val=REJECT
- **PG** [PDEC-PG-0018] signal=STRONG BUY → HOLD_PAPER → MISSING (other) → PnL $16.67 / val=CONTINUE_TESTING
- **SPY** [PDEC-SPY-0024] signal=STRONG BUY → HOLD_PAPER → MISSING (other) → PnL $-6.33 / val=CONTINUE_TESTING
- **PM** [PDEC-PM-0019] signal=STRONG BUY → HOLD_PAPER → MISSING (other) → PnL $-27.46 / val=CONTINUE_TESTING
- **AIR.PA** [PDEC-AIR.PA-0003] signal=WAIT → HOLD_PAPER → MISSING (cooldown_reentry_churn) → PnL $-0.30 / val=CONTINUE_TESTING
- **MC.PA** [PDEC-MC.PA-0013] signal=WAIT → HOLD_PAPER → MISSING (cooldown_reentry_churn) → PnL $3.75 / val=CONTINUE_TESTING
- **ULVR.L** [PDEC-ULVR.L-0025] signal=WAIT → SKIP_PAPER → MISSING (policy_skip) → PnL $0.00 / val=NEEDS_MORE_DATA
- **AMAT** [PDEC-AMAT-0005] signal=STRONG BUY → SKIP_PAPER → MISSING (policy_skip) → PnL $0.00 / val=NEEDS_MORE_DATA
- **MU** [PDEC-MU-0016] signal=WAIT → SKIP_PAPER → MISSING (policy_skip) → PnL $0.00 / val=NEEDS_MORE_DATA
- … +10 more in `tae_profit_pipeline.json`
