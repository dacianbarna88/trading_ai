# TAE Structural Governance Report

**Generated:** 2026-09-03T13:15:21+00:00
**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_PROMOTION
**Final verdict:** **READY_FOR_PAPER_DAY**

## Execution hierarchy (mandatory order)

| rank | layer | class | status | reason |
| ---: | --- | --- | --- | --- |
| 1 | DATA VALIDITY | HARD | **PASS** | - |
| 1 | ACCOUNTING SNAPSHOT | HARD | **PASS** | - |
| 1 | PROTECT SHADOW | HARD | **PASS** | - |
| 1 | PORTFOLIO PROTECT | HARD | **PASS** | - |
| 1 | ADAPTIVE POLICY | HARD | **PASS** | - |
| 1 | GROWTH INTELLIGENCE | HARD | **PASS** | - |
| 1 | INFRASTRUCTURE HEALTH | HARD | **PASS** | - |
| 1 | ADAPTIVE DEPLOYMENT STATUS | HARD | **PASS** | - |
| 2 | ACCOUNTING RECONCILIATION | HARD | **PASS** | - |
| 2 | ACCOUNTING RECONCILIATION (post-MTM) | HARD | **PASS** | - |
| 3 | CAPITAL SAFETY | HARD | **PASS** | - |
| 4 | HARD RISK RULES | HARD | **PASS** | - |
| 4 | HARD RISK RULES (post-MTM) | HARD | **PASS** | - |
| 5 | POSITION DISCIPLINE | HARD | **PASS** | - |
| 6 | PROFIT PROTECTION | POLICY | **PASS** | - |
| 7 | LOSS CUTTING | POLICY | **PASS** | - |
| 8 | BUY ELIGIBILITY | POLICY | **PASS** | - |
| 9 | POLICY LAYER | POLICY | **PASS** | - |
| 10 | LEARNING / ADAPTIVE LAYER | LEARNING | **PASS** | - |
| 10 | DECISION STATE | LEARNING | **PASS** | - |
| 10 | CONFLICT RESOLUTION | LEARNING | **PASS** | - |
| 10 | KNOWLEDGE BASE VIEW | LEARNING | **PASS** | - |
| 10 | PAPER EXPERIMENTS | LEARNING | **PASS** | - |
| 11 | PAPER EXECUTION | HARD | **PASS** | - |
| 12 | MARK-TO-MARKET | HARD | **PASS** | - |
| 12 | MARK-TO-MARKET (final) | HARD | **PASS** | - |
| 12 | DUAL STRATEGY V1+V2 | LEARNING | **PASS** | - |
| 13 | OUTCOME MEMORY | LEARNING | **PASS** | - |
| 14 | RULE SURVIVAL | LEARNING | **PASS** | - |
| 15 | ADAPTIVE WEIGHTS | LEARNING | **PASS** | - |
| 16 | CONSTITUTIONAL EVOLUTION | LEARNING | **PASS** | - |
| 16 | POST-LEARNING EXECUTION | HARD | **PASS** | - |
| 17 | DPE | LEARNING | **PASS** | - |
| 17 | SELF-IMPROVE | LEARNING | **PASS** | - |
| 18 | CANONICAL VS PAPER | REPORT_ONLY | **PASS** | - |
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

- none

## Block reasons

- none
