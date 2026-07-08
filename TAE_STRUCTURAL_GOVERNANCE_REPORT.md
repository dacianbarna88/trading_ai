# TAE Structural Governance Report

**Generated:** 2026-07-08T15:51:17+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Final verdict:** **READY_FOR_PAPER_DAY**

## Execution hierarchy (mandatory order)

| rank | layer | class | status | reason |
| ---: | --- | --- | --- | --- |
| 1 | DATA VALIDITY | HARD | **PASS** | - |
| 2 | ACCOUNTING RECONCILIATION | HARD | **PASS** | - |
| 2 | ACCOUNTING RECONCILIATION (post-MTM) | HARD | **PASS** | - |
| 3 | CAPITAL SAFETY | HARD | **PASS** | - |
| 4 | HARD RISK RULES | HARD | **BREACH** | 1 breach(es) — HARD SELL override required |
| 4 | HARD RISK RULES (post-MTM) | HARD | **PASS** | - |
| 5 | POSITION DISCIPLINE | HARD | **PASS** | - |
| 6 | PROFIT PROTECTION | POLICY | **PASS** | - |
| 7 | LOSS CUTTING | POLICY | **PASS** | - |
| 8 | BUY ELIGIBILITY | POLICY | **PASS** | - |
| 9 | POLICY LAYER | POLICY | **PASS** | - |
| 10 | LEARNING / ADAPTIVE LAYER | LEARNING | **PASS** | - |
| 11 | PAPER EXECUTION | HARD | **PASS** | - |
| 12 | MARK-TO-MARKET | HARD | **PASS** | - |
| 13 | OUTCOME MEMORY | LEARNING | **PASS** | - |
| 14 | RULE SURVIVAL | LEARNING | **PASS** | - |
| 15 | ADAPTIVE WEIGHTS | LEARNING | **PASS** | - |
| 16 | DPE | LEARNING | **PASS** | - |
| 17 | CANONICAL VS PAPER | REPORT_ONLY | **PASS** | - |
| 18 | PROMOTION LOCK | HARD | **PASS** | - |
| 19 | FINAL VERDICT | HARD | **READY_FOR_PAPER_DAY** | - |

## Hard rules enforced

- STOP_LOSS_-3% (hard_risk_guardian → PDE override → SELL_PAPER)
- CRITICAL_LOSS_-5% (FORCE_SELL_REQUIRED)
- No PROTECT/SELL/REDUCE without PAPER position (PDE + execution)
- DISABLED rules cannot boost scores (rule_lifecycle + PDE)
- Unreconciled PAPER accounting blocks cycle
- broker_executed=false, live_money=false required
- live_promotion_allowed=false (promotion lock)
- Forbidden live path diff must be 0

## Overrides

- QQQ: SELL_REQUIRED at -3.212% (HARD_STOP_LOSS_-3)

## Block reasons

- none
