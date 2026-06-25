# TAE Roadmap

**Trading AI Ecosystem — Version Plan**

Version: Foundation Sprint 1  
Status: RESEARCH_ONLY | NO_BROKER | NO_EXECUTION

---

## Roadmap Philosophy

Each TAE major version adds a **civilizational capability** — not merely a script. Versions are gated by documentation, validation, and ecosystem health — not by broker connectivity.

**Broker is last, not first.**

---

## Version Overview

| Version | Name | Core capability | Broker? |
|---------|------|-----------------|---------|
| **TAE 1.0** | Foundation | Research chain, organisms as modules, docs | No |
| **TAE 2.0** | Adaptive Intelligence | Knowledge Core v1, trust, evolution | No |
| **TAE 3.0** | Collective Intelligence | Organism bus, packet protocol, consensus | No |
| **TAE 4.0** | Paper Decision System | Paper labels → tracked outcomes | Paper only |
| **TAE 5.0** | Broker-Ready System | Gated live connectivity | Optional last |

---

## TAE 1.0 — Foundation

**Status:** In progress (Sprint 1)

### Goals

- Document ecosystem architecture, vision, organism contract, Knowledge Core spec
- Establish `research_core` as shared research framework
- Ship research pipeline: Discovery → Ensemble → Evidence
- Prove explainable scores improve returns in backtest

### Deliverables (existing / Sprint 1)

| Artifact | Role |
|----------|------|
| `TAE_*.md` | Foundation documentation |
| `research_core/` | Modular research framework |
| `edge_discovery_engine_v30.py` | Pattern discovery organism |
| `edge_ensemble_engine_v31.py` | Consensus organism |
| `evidence_engine_v40.py` | Evidence / dossier organism |
| Context, momentum, liquidity, recovery modules | Organism precursors |

### Exit criteria

- [ ] All foundation docs complete
- [ ] Discovery → Ensemble → Evidence runs end-to-end on universe
- [ ] Every score has human explanation in outputs
- [ ] No modifications to live execution paths
- [ ] `EVIDENCE_ENGINE_CONFIRMED` or documented partial result

### Not in 1.0

- Knowledge Core database
- Organism message bus
- Paper portfolio tracking
- Broker integration

---

## TAE 2.0 — Adaptive Intelligence

### Goals

- Implement **Memory Organism** per `TAE_KNOWLEDGE_CORE_SPEC.md`
- File/SQLite Knowledge Core with import adapters from CSV outputs
- **Evolution Layer v1:** trust scores, archive weak patterns, promote robust
- **Learning Organism** wired to meta-analysis and false-decision feedback
- Weight recalibration from bucket performance drift

### Key modules

| Module | Function |
|--------|----------|
| `tae_knowledge/` package | Pattern, evidence, trust stores |
| `tae_evolution/` | Trust updates, archive/promote rules |
| Import pipelines | Survivors, dossiers, ensemble stats → Core |
| Trust dashboard (research) | Trust distribution visualization |

### Exit criteria

- Patterns have `status`, `trust_score`, success/failure conditions in Core
- Evolution run archives at least one weak candidate with audit reason
- Organism trust scores influence ensemble weights
- Full lineage for promote/archive events

### Not in 2.0

- Live or paper order placement
- Real-time organism bus
- Broker API

---

## TAE 3.0 — Collective Intelligence

### Goals

- Formal **Organism Registry** and evidence packet protocol
- All active organisms emit `EvidencePacket` schema (see Organism Contract)
- **Collective Intelligence bus** — organisms publish; consensus layer subscribes
- Family diversification and conflict detection as shared library
- **Ecosystem Health metrics** v1 automated

### Key capabilities

| Capability | Description |
|------------|-------------|
| Packet bus | In-process or file-queue evidence exchange |
| Consensus service | Weighted fusion with trust + diversification |
| Organism health | Stability, output variance, error rates |
| Missing organism detection | Flag domains without active observer |
| Context, Liquidity, Risk organisms | Upgraded to packet-compliant outputs |

### Exit criteria

- ≥5 organisms registered and emitting packets
- Consensus reproducible from packet archive alone
- Health dashboard: Knowledge Growth, False Decision Rate (research labels)
- No organism bypasses explanation requirement

### Not in 3.0

- Paper execution
- Broker

---

## TAE 4.0 — Paper Decision System

### Goals

- **Decision Organism** consumes HIGH_CONVICTION dossiers
- Paper portfolio simulator (separate from `portfolio.csv` — new research file)
- Track paper entries from `Decision_Label` with full evidence trail
- Outcome feedback loop → Evolution Layer trust updates
- Human approval gate for production candidate queue

### Key capabilities

| Capability | Description |
|------------|-------------|
| Paper signal journal | `tae_paper_journal.csv` (research only) |
| Outcome evaluator | Compare paper label vs realized forward return |
| False decision rate | Automated metric |
| Production candidate queue | Human review UI or structured CSV |
| Validation horizon engine | Multi-window outcome checks |

### Hard rules (carry forward)

- `portfolio.csv` untouched unless explicit future sprint
- `live_bot.py` untouched
- `dashboard_v2.py` untouched
- PAPER_ONLY — simulated fills, no broker orders

### Exit criteria

- Paper journal tracks ≥100 HIGH_CONVICTION candidates with dossiers linked
- False decision rate computed and fed to Evolution
- Production candidates require human `APPROVED` flag in Knowledge Core

---

## TAE 5.0 — Broker-Ready System

### Goals

- **Broker adapter layer** (isolated module — not embedded in organisms)
- Consumes only `APPROVED` Knowledge Core entries with full lineage
- Pre-trade evidence packet attached to every intended action
- Kill switch, max risk, and human override mandatory
- Gradual rollout: paper → micro-live → scaled

### Architecture principle

```
Knowledge Core (APPROVED only)
        │
        ▼
  Decision Gate (human + risk)
        │
        ▼
  Broker Adapter (last mile)
        │
        ▼
     Market
```

Organisms **never** call the broker. Only the gated adapter does.

### Exit criteria

- Zero organism imports broker SDK
- Every live intent traceable to evidence_id + pattern_id + run_id
- Rollback: disable adapter without breaking research pipeline

### Explicitly not automatic in 5.0

- Full autonomous trading without human gate
- Modification of legacy `live_bot.py` without dedicated migration sprint

---

## Cross-Version Dependencies

```
TAE 1.0 Foundation
    │
    ├── research_core framework
    ├── Discovery / Ensemble / Evidence
    └── TAE documentation
            │
            ▼
TAE 2.0 Adaptive Intelligence
    │
    ├── Knowledge Core v1
    ├── Evolution Layer v1
    └── Trust model
            │
            ▼
TAE 3.0 Collective Intelligence
    │
    ├── Organism Registry
    ├── Evidence packet bus
    └── Health metrics
            │
            ▼
TAE 4.0 Paper Decision System
    │
    ├── Paper journal
    ├── Outcome feedback
    └── Human approval queue
            │
            ▼
TAE 5.0 Broker-Ready System
    │
    └── Gated broker adapter only
```

---

## Sprint Mapping (Near Term)

| Sprint | Focus |
|--------|-------|
| **Sprint 1** (current) | TAE docs, research_core, Discovery/Ensemble/Evidence |
| Sprint 2 | Knowledge Core import adapters, pattern status model |
| Sprint 3 | Evolution Layer v1, trust updates |
| Sprint 4 | Organism packet schema in code |
| Sprint 5 | Collective Intelligence bus prototype |
| Sprint 6+ | Paper decision system design |

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Premature broker connection | Roadmap gates; broker only in 5.0 |
| Black-box scores | Organism Contract + Evidence Engine |
| Knowledge loss (CSV-only) | Knowledge Core in 2.0 |
| Organism duplication | Family diversification + Evolution archive |
| Live bot contamination | Hard rule: no edits to live paths in research sprints |
| Overfitting promotion | WF + ensemble + evidence monotonicity gates |

---

## Success Metrics by Version

| Version | Primary metric |
|---------|----------------|
| 1.0 | Evidence engine confirms score→return relationship |
| 2.0 | Trust score predicts organism accuracy |
| 3.0 | Consensus from packets matches monolithic ensemble |
| 4.0 | Paper false decision rate < threshold |
| 5.0 | 100% trade intent traceability to evidence |

---

## Related Documents

- `TAE_VISION.md`
- `TAE_ARCHITECTURE.md`
- `TAE_ORGANISM_CONTRACT.md`
- `TAE_KNOWLEDGE_CORE_SPEC.md`

---

*RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION*
