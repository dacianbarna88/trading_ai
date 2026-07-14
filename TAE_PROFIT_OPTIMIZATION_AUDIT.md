# TAE Profit Optimization Audit

**Generated:** 2026-07-14
**Verdict:** `CURRENT_BRAIN_RETAINED_INSUFFICIENT_EVIDENCE`
**Mode:** PAPER_ONLY · READ_ONLY · AUDIT_FIRST

## Phase 1 — Clean evidence set

- Clean window start: `2026-07-08T20:57:01+00:00`
- Usable sessions: **4** (2026-07-08, 2026-07-09, 2026-07-10, 2026-07-13)
- Usable decisions: **25**
- Usable orders (deduped): **25**
- Usable executions: **16**
- Usable closed outcomes: **4**
- Incomplete outcomes: **21**
- Exclusions: {'synthetic_100_fill': 2, 'duplicate_order_superseded': 27}

## Phase 2 — Attribution highlights

- Opportunity cost (shadow ledger): **$829.72**
- Top ticker PnL: {'AAPL': 35.2363, 'PG': 16.6722, 'MC.PA': 3.7492, 'AIR.PA': -0.298, 'QQQ': -5.4054, 'SPY': -6.33, 'GE': -7.2393, 'HSBA.L': -9.2735, 'AMAT': -22.9851, 'PM': -27.4632, 'LLY': -35.1205, 'MRK': -39.1512, 'SIE.DE': -142.4888, 'MU': -163.0994}
- DPE collaborative PF: **1.0344**

## Phase 3 — Top profit blockers

1. **open_loser_hold_drag** — impact ~$130.28 (strength MODERATE, risk LOW)
2. **hard_risk_crystallized_realized_losses** — impact ~$450.98 (strength HIGH, risk HIGH)
3. **policy_skip_capital_preservation** — impact ~$124.46 (strength LOW, risk MEDIUM)
4. **stale_mark_blocks_buy** — impact ~$0.0 (strength MODERATE, risk LOW)
5. **post_stop_rebuy_churn** — impact ~$22.99 (strength MODERATE, risk LOW)

## Phase 6 — Selection

- **CURRENT_BRAIN_RETAINED_INSUFFICIENT_EVIDENCE**
- Reason: No challenger beat baseline PnL with multi-ticker/multi-session robustness on clean evidence.

## Integrity

- Profit integrity: **PAPER_PROFIT_INTEGRITY_CLOSED**
- Reconciliation: **PASS**
- promotion_lock: **false**
