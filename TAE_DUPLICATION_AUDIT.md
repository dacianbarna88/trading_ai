# TAE Duplication Audit — X.AUDIT

**Date:** 2026-07-06  
**Mode:** READ_ONLY

Classification: **REUSE** · **MERGE** · **EXTEND** · **ARCHIVE** · **KEEP_SEPARATE**

---

## 1. Profit protection

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| Protection shadow snapshot | `tae_profit_protection_shadow.py` in market-open step 5 **and** protect CLI step 1 | **REUSE** | Same script, two orchestrators — not duplicate code |
| Rules v1 logic | Shadow rules vs PIB PSP vs PDC rules vote | **KEEP_SEPARATE** | Different layers: rules / survival / committee |
| Historical validation | `tae_profit_protection_validation.py` vs replay/knowledge | **EXTEND** | Validation owns gates; replay owns sequencing — link via knowledge |
| Missed opportunity USD | Shadow global summary vs fade history vs PPG aggregate | **REUSE** | Shadow JSON as SSOT; others reference |

**Verdict:** Profit protection stack is **layered, not duplicated**. Do not rebuild — **extend** PCE/APPE.

---

## 2. Profit decision

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| Committee v1 vs weighted v2 | `tae_profit_decision_committee.py` + learning | **EXTEND** | Same module family |
| Context v1 additive vs v2 weighted | `tae_profit_context_engine.py` | **REUSE** | v2 replaced v1 in place |
| Profit PDG vs global decision governor | `tae_profit_decision_governor.py` vs `tae_decision_governor.py` | **KEEP_SEPARATE** | Different domains (open book vs universe) |
| PDC recommendation vs PDG final rec | Committee vs governor reconcile | **KEEP_SEPARATE** | Governor is VIEW composer |

**Verdict:** **Do not merge** governors. **Reuse** PDG+PPG as profit decision display layer.

---

## 3. Portfolio risk

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| Portfolio profit governor vs portfolio reconciliation | PPG vs `tae_portfolio_reconciliation.py` | **KEEP_SEPARATE** | PPG = profit posture; reconciliation = SELL integrity |
| Regional risk in PPG vs macro runtime | PPG suffix inference vs `tae_macro_runtime` | **EXTEND** | PPG heuristic is thin — could ingest macro later |
| Concentration score in PPG vs allocation enrich | PPG internal vs `tae_live_signals_allocation_enrich` | **KEEP_SEPARATE** | Different purposes until unified portfolio risk model |

---

## 4. Confidence

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| Signal confidence evolution | `tae_confidence_evolution.py` | **KEEP_SEPARATE** | Pre-entry signal decay |
| Profit decision confidence | PDC/PCE/PDG per-ticker | **KEEP_SEPARATE** | Post-entry protection |
| Advisory confidence | `tae_live_advisory.json` | **KEEP_SEPARATE** | Live gate |
| Committee runtime confidence | `tae_committee_runtime.py` | **ARCHIVE** (for live profit path) | Macro committee — legacy advisory path |

**Recommendation:** **MERGE** naming/docs only — not code. Three confidence domains are valid.

---

## 5. Learning

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| Committee member learning | `tae_profit_committee_learning.py` | **REUSE** | SSOT for member weights |
| Context weight learning | `tae_profit_context_learning.json` | **REUSE** | SSOT for context weights |
| Adaptive profit policy | `tae_adaptive_profit_policy_engine.py` | **EXTEND** | Portfolio-level; young memory |
| Knowledge base | `tae_knowledge_base.py` | **REUSE** | Cross-domain VIEW — ingest, don't rewrite |
| Learning runtime | `tae_learning_runtime.py` | **ARCHIVE** | Superseded by specific learners |

**Verdict:** **Do not** create a fourth learning store — **extend** APPE and feed validated outcomes into knowledge base ingest.

---

## 6. Knowledge

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| Knowledge base VIEW | `tae_knowledge_base.py` | **REUSE** | Materialized aggregator |
| Profit memory episodes | `tae_profit_memory_engine.json` | **KEEP_SEPARATE** | SSOT for episodes; knowledge ingests summaries |
| Event memory runtime | `tae_event_memory_runtime.py` | **ARCHIVE** (pending) | Scaffold — 0 live events |
| Knowledge in protect shadow | `knowledge_trailing_priority` flag | **REUSE** | Reads knowledge JSON |

---

## 7. Accounting

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| Accounting snapshot | `research_core/accounting/accounting_snapshot.py` | **REUSE** | Canonical PnL |
| Dashboard open PnL | `dashboard_v2.py compute_open_positions` | **MERGE** (future) | Should read snapshot or shared parser |
| Full ecosystem review PnL | `tae_full_ecosystem_review.py` | **EXTEND** | Should prefer snapshot fields |
| Capital base integrity | Separate audit JSON | **KEEP_SEPARATE** | Integrity layer on snapshot |

---

## 8. Market readiness

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| Infrastructure health | `tae_infrastructure_health.py` | **REUSE** | Process/cron SSOT |
| Quick health check | `tae_quick_health_check.py` | **EXTEND** | Should call infra health + key JSON freshness |
| Startup verify | `tae_startup_verify.py` | **KEEP_SEPARATE** | Post-boot smoke |
| Market open monitor | `tae_market_open_monitor.py` | **KEEP_SEPARATE** | Runner-specific |

---

## 9. Startup / health / infrastructure

| Overlap | Modules | Classification | Rationale |
|---------|---------|----------------|-----------|
| `market_open_runner.sh` vs `tae_startup_launcher.py` | Shell vs Python launcher | **KEEP_SEPARATE** | Different triggers |
| Intelligence runner lock vs bot pgrep | Runner `.lock` vs shell pgrep | **KEEP_SEPARATE** | OK |
| Multiple `tae_*_runtime.py` enrichers | 12+ runtime builders | **ARCHIVE** candidates | Many unused in profit path — audit before extend |

---

## 10. Legacy duplication (high noise)

| Pattern | Count | Classification |
|---------|-------|----------------|
| `tae_phase*_demo.py` | 40+ | **ARCHIVE** — not production |
| Root outcome engines (V14) | 3–5 files | **ARCHIVE** — not X.9 schema |
| `live_bot_v5_1.py` | 1 | **ARCHIVE** |
| Dual scanner paths | scanner_refresh vs unified | **ARCHIVE** old path when unified stable |

---

## Priority actions (no rebuild)

| Priority | Action | Type |
|----------|--------|------|
| 1 | Shared read-only portfolio position parser | EXTEND |
| 2 | Dashboard PnL from accounting snapshot | REUSE |
| 3 | Wire APPE validated outcomes → knowledge ingest | EXTEND |
| 4 | Document dual-governor boundaries | KEEP_SEPARATE |
| 5 | Archive phase demos from operational docs | ARCHIVE |

---

**READ_ONLY audit — no files modified.**
