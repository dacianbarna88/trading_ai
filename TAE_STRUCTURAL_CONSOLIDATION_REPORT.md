# TAE Structural Consolidation Report

**Generated:** 2026-09-11T13:14:46+00:00
**Final verdict:** **BLOCKED_WITH_REASONS**

## Modules consolidated

| module | role | status |
| --- | --- | --- |
| `hard_risk_guardian.py` | HARD | ACTIVE |
| `tae_paper_decision_engine.py` | HARD/POLICY | ACTIVE |
| `tae_paper_execution.py` | HARD | ACTIVE |
| `tae_rule_survival.py` | LEARNING | ACTIVE |
| `tae_adaptive_paper_weights.py` | LEARNING | ACTIVE |
| `tae_longitudinal_outcome_memory.py` | LEARNING | ACTIVE |
| `tae_live_promotion_lock.py` | HARD | ACTIVE |
| `tae_portfolio_profit_governor.py` | POLICY | UPSTREAM_SHADOW |
| `tae_adaptive_profit_policy_engine.py` | POLICY | UPSTREAM_SHADOW |
| `tae_profit_decision_governor.py` | POLICY | UPSTREAM_SHADOW |
| `tae_profit_protection_validation.py` | POLICY | UPSTREAM_SHADOW |
| `tae_decision_governor.py` | OBSERVABILITY_ONLY | OBSERVABILITY |
| `tae_knowledge_base.py` | LEARNING | ACTIVE |
| `tae_portfolio_reconciliation.py` | REPORT_ONLY | LEGACY_LIVE_AUDIT |
| `tae_dpe_*` | LEARNING | ACTIVE |

## PAPER result

- Portfolio value: **$29,754.83**
- Cash: **$129.33**
- Realized PnL: **$-427.00**
- Unrealized PnL: **$-159.09**
- Total PnL: **$-586.09**
- Reconciliation: **PASS**
- Hard risk: **PASS** (0 breaches)
- Canonical vs PAPER delta: **$-109.71**

## Files changed (this consolidation)

- `tae_structural_governance.py`
- `hard_risk_guardian.py` (PAPER adapter)
- `tae_full_paper_cycle.py` (structural delegate)
- `tae_paper_decision_engine.py` (hard risk consume)
- `TAE_STRUCTURAL_GOVERNANCE.md`

## Operator command

```bash
python3 tae.py full-paper-cycle
```
