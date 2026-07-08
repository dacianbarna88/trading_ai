# TAE Structural Governance

**Mode:** PAPER_ONLY | NO_BROKER | NO_LIVE_PROMOTION  
**Authority:** `tae_structural_governance.py` — single orchestrator for the PAPER ecosystem.

## Mandatory execution hierarchy

Every PAPER cycle step runs in this order. Hard layers block downstream authority; policy and learning layers cannot override hard rules.

| Rank | Layer | Class | Module(s) |
| ---: | --- | --- | --- |
| 1 | DATA VALIDITY | HARD | `tae_historical_runtime_refresh.py` |
| 2 | ACCOUNTING RECONCILIATION | HARD | `tae_paper_execution.validate_portfolio_reconciliation()` |
| 3 | CAPITAL SAFETY | HARD | PAPER portfolio flags + APPE policy |
| 4 | HARD RISK RULES | HARD | `hard_risk_guardian.py` → `runtime_outputs/governance/hard_risk.json` |
| 5 | POSITION DISCIPLINE | HARD | `tae_paper_decision_engine.enforce_position_discipline()` |
| 6 | PROFIT PROTECTION | POLICY | PDE + shadow governors (upstream JSON) |
| 7 | LOSS CUTTING | POLICY | PDE `enforce_loss_discipline()` (-5%/-7% soft) |
| 8 | BUY ELIGIBILITY | POLICY | PDE buy scoring + capital hints |
| 9 | POLICY LAYER | POLICY | APPE / hypothesis rules |
| 10 | LEARNING / ADAPTIVE | LEARNING | `learning-profit` (pre-decision hypothesis queue) |
| 11 | PAPER EXECUTION | HARD | `tae_paper_execution.py` |
| 12 | MARK-TO-MARKET | HARD | `tae_paper_execution` MTM |
| 13 | OUTCOME MEMORY | LEARNING | `tae_longitudinal_outcome_memory.py` |
| 14 | RULE SURVIVAL | LEARNING | `tae_rule_survival.py` |
| 15 | ADAPTIVE WEIGHTS | LEARNING | `tae_adaptive_paper_weights.py` |
| 16 | DPE | LEARNING | `tae_dpe_*` chain |
| 17 | CANONICAL VS PAPER | REPORT_ONLY | canonical-vs-paper CLI |
| 18 | PROMOTION LOCK | HARD | `tae_live_promotion_lock.py` |
| 19 | FINAL VERDICT | HARD | `tae_structural_governance.compute_final_verdict()` |

## Rule classification

| Class | Meaning | Override authority |
| --- | --- | --- |
| **HARD** | Safety, accounting, position, execution, promotion | Blocks cycle; cannot be softened |
| **POLICY** | Profit protection, loss cutting, buy eligibility | Applied inside PDE after hard gates |
| **LEARNING** | Outcome memory, rule survival, adaptive weights, DPE | Influences scores; never bypasses HARD |
| **REPORT_ONLY** | Canonical vs PAPER, legacy audits | Observability only |
| **LEGACY** | Live CSV governors, shadow-only modules | Not in PAPER cycle authority |

## Hard rules enforced

1. **STOP_LOSS -3%** — `hard_risk_guardian` writes breach; PDE `enforce_hard_risk_discipline()` forces `SELL_PAPER` before soft logic.
2. **CRITICAL_LOSS -5%** — `FORCE_SELL_REQUIRED` at hard layer.
3. **No SELL/PROTECT/REDUCE/ROTATE without PAPER position** — PDE + execution `SKIPPED_NO_POSITION`.
4. **DISABLED rules** — rule lifecycle reduces influence; cannot boost scores.
5. **Unreconciled accounting** — reconciliation FAIL blocks final verdict.
6. **Stale critical data** — rank-1 gate FAIL blocks cycle.
7. **broker_executed / live_money** — capital safety FAIL.
8. **live_promotion_allowed=false** — promotion lock always enforced.
9. **Forbidden path diff = 0** — `live_bot.py`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt`, `core/`, `research_core/`.

## Module registry

| Module | Role | Cycle status |
| --- | --- | --- |
| `hard_risk_guardian.py` | HARD risk | ACTIVE (PAPER adapter) |
| `tae_paper_decision_engine.py` | HARD/POLICY decisions | ACTIVE |
| `tae_paper_execution.py` | HARD execution + reconciliation | ACTIVE |
| `tae_rule_survival.py` | LEARNING lifecycle | ACTIVE |
| `tae_adaptive_paper_weights.py` | LEARNING weights | ACTIVE |
| `tae_longitudinal_outcome_memory.py` | LEARNING memory | ACTIVE |
| `tae_live_promotion_lock.py` | HARD promotion block | ACTIVE |
| `tae_portfolio_profit_governor.py` | POLICY upstream | UPSTREAM_SHADOW |
| `tae_adaptive_profit_policy_engine.py` | POLICY upstream | UPSTREAM_SHADOW |
| `tae_profit_decision_governor.py` | POLICY upstream | UPSTREAM_SHADOW |
| `tae_profit_protection_validation.py` | POLICY upstream | UPSTREAM_SHADOW |
| `tae_decision_governor.py` | LEGACY advisory | LEGACY_SHADOW |
| `tae_portfolio_reconciliation.py` | REPORT_ONLY live audit | LEGACY_LIVE_AUDIT |
| `tae_dpe_*` | LEARNING competitive/collaborative | ACTIVE |

## Outputs

| Path | Purpose |
| --- | --- |
| `runtime_outputs/governance/structural_governance.json` | Full step trace + verdict |
| `runtime_outputs/governance/hard_risk.json` | Hard risk evaluation |
| `TAE_STRUCTURAL_GOVERNANCE_REPORT.md` | Operator governance report |
| `TAE_STRUCTURAL_CONSOLIDATION_REPORT.md` | Consolidation summary |
| `runtime_outputs/full_paper_cycle/summary.json` | Legacy-compatible cycle summary |

## Operator command

```bash
python3 tae.py full-paper-cycle
```

## Forbidden (never modified by PAPER cycle)

- `live_bot.py`, `portfolio.csv`, `live_signals.csv`, `watchlist.txt`
- `core/`, `research_core/`
- Broker execution, real money, live promotion
