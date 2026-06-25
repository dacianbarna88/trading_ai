# TAE Architecture

**Trading AI Ecosystem — System Architecture**

Version: Foundation Sprint 1  
Status: RESEARCH_ONLY | NO_BROKER | NO_EXECUTION

---

## Overview

TAE is organized as a **layered living ecosystem**. Data enters through the Market Layer; specialized **Organisms** interpret it; **Collective Intelligence** fuses their outputs; the **Knowledge Core** persists validated learning; the **Evolution Layer** updates trust and archives weak beliefs; **Ecosystem Health** metrics monitor whether the civilization is learning well.

```
                    ┌─────────────────────────────────────┐
                    │         ECOSYSTEM HEALTH            │
                    │  (metrics, audits, quality gates)   │
                    └─────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼───────────────────────────────┐
    │                               │                               │
    ▼                               ▼                               ▼
┌─────────┐              ┌──────────────────┐              ┌─────────────┐
│ MARKET  │──data───────▶│  ORGANISM LAYER  │──evidence──▶│ KNOWLEDGE   │
│  LAYER  │              │  (10 organisms)  │             │    CORE     │
└─────────┘              └────────┬─────────┘              └──────┬──────┘
                                  │                               │
                                  ▼                               │
                         ┌──────────────────┐                     │
                         │ COLLECTIVE       │◀────────────────────┘
                         │ INTELLIGENCE     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ EVOLUTION LAYER  │
                         │ trust · archive  │
                         │ promote · weight │
                         └──────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────────┐
                    │   FUTURE: Paper / Broker (TAE 4–5)  │
                    │   Consumes decision packets only    │
                    └─────────────────────────────────────┘
```

---

## 1. Market Layer

The Market Layer is the **sensory input** of the ecosystem. It does not trade. It normalizes what exists in the world.

| Domain | Examples | Notes |
|--------|----------|-------|
| **Price** | OHLCV, gaps, returns, SMA distances | Daily research baseline today |
| **Volume** | Volume ratio, dollar volume, participation | Liquidity context |
| **Volatility** | ATR, range expansion, vol regimes | Risk and sizing research |
| **Macro** | SPY regime, index trend, rates (future) | Market context for edges |
| **News** | Headlines, sentiment (future) | Not in Sprint 1 |
| **Sectors** | Sector rotation, concentration | Diversification checks |
| **Liquidity** | Spread proxies, sweep patterns | Liquidity Organism input |
| **Options** | IV, skew, flow (future) | Planned extension |

**Contract:** Market Layer outputs **normalized feature frames** — timestamped, ticker-scoped, auditable — never trade instructions.

**Current implementation touchpoints:** `yfinance` history, `us_expanded_universe.txt`, `research_core` MarketDataService, context enrichment pipelines.

---

## 2. Organism Layer

Organisms are **specialized research agents**. Each observes a domain, produces evidence, and participates in collective intelligence. They do not execute orders.

| Organism | Primary domain | Precursor in Trading AI |
|----------|----------------|-------------------------|
| **Context Organism** | Regime, macro alignment, environmental fit | V1.8 context intelligence |
| **Momentum Organism** | Continuation strength, threshold behavior | V1.1 / V1.3 momentum research |
| **Liquidity Organism** | Sweeps, volume anomalies, participation | V1.7 liquidity sweep |
| **Recovery Organism** | Drawdown recovery, re-entry logic | V1.5 recovery intelligence |
| **Volatility Organism** | ATR regimes, expansion/contraction | Feature bins, ATR research |
| **Risk Organism** | MAE, tail risk, concentration | V1.4 position mgmt, robustness |
| **Evidence Organism** | Dossiers, decision labels, explanations | V4.0 Evidence Engine |
| **Learning Organism** | Meta-analysis, direction finding | V1.6 research direction |
| **Memory Organism** | Persistence, retrieval, lineage | Knowledge Core (spec) |
| **Decision Organism** | Paper labels, consensus packets | V3.1 ensemble + V4.0 evidence |

Every organism adheres to the **Organism Contract** (`TAE_ORGANISM_CONTRACT.md`).

---

## 3. Organism Contract (Summary)

Each organism must answer seven questions (full spec in `TAE_ORGANISM_CONTRACT.md`):

1. What do you observe?
2. What do you understand?
3. What evidence do you produce?
4. How confident are you?
5. How do you explain your conclusion?
6. What did you learn?
7. How do you help the ecosystem?

No organism ships without auditable answers.

---

## 4. Knowledge Core

The Knowledge Core is TAE's **long-term memory and trust registry**. See `TAE_KNOWLEDGE_CORE_SPEC.md`.

Stores: validated patterns, evidence artifacts, confidence, trust, status, history, evolution logs, success/failure conditions.

Organisms **write proposals**; validation pipelines **promote** entries; Evolution Layer **updates trust**.

---

## 5. Collective Intelligence

Organisms do not vote silently. They exchange **evidence packets**:

```
┌──────────────┐     evidence packet      ┌──────────────┐
│  Organism A  │ ────────────────────────▶│  Consensus   │
│  (Context)   │   score · trust · text   │  Formation   │
└──────────────┘                          └──────┬───────┘
┌──────────────┐                                 │
│  Organism B  │ ────────────────────────────────┤
│  (Momentum)  │                                 ▼
└──────────────┘                          ┌──────────────┐
┌──────────────┐                          │ Edge /       │
│  Organism C  │ ────────────────────────▶│ Evidence   │
│  (Risk)      │                          │ Consensus  │
└──────────────┘                          └──────────────┘
```

**Packet contents:**

| Field | Purpose |
|-------|---------|
| `organism_id` | Source identity |
| `observation_scope` | Ticker, date, signal_id |
| `evidence_score` | 0–100 domain score |
| `confidence` | Calibrated belief strength |
| `trust` | Historical reliability of this organism |
| `explanation` | Human-readable reasoning |
| `artifacts` | Paths or hashes to CSV/dossier outputs |
| `timestamp` | Audit trail |

**Consensus formation** (research stage):

- Weighted fusion similar to Edge Ensemble (V3.1) and Evidence Engine (V4.0)
- Family diversification — correlated organisms do not stack blindly
- Conflict detection — contradictory packets reduce consensus
- Output: `Edge_Consensus_Score`, `Overall_Evidence_Score`, `Decision_Label` (research only)

---

## 6. Evolution Layer

TAE learns from outcomes without reckless self-modification.

| Mechanism | Behavior |
|-----------|----------|
| **False decision tracking** | Paper labels that underperform baseline feed Learning Organism |
| **Trust updates** | Organisms with predictive evidence gain trust; noisy ones lose |
| **Archive weak edges** | Patterns below validation thresholds → `ARCHIVED` status |
| **Promote robust edges** | Survivors with walk-forward + ensemble support → `VALIDATED` |
| **Weight recalibration** | Ensemble/evidence weights adjust from bucket performance |
| **Missing organism detection** | Health metrics flag domains with no active observer |

Evolution is **governed** — humans approve promotion to production candidates.

---

## 7. Ecosystem Health (Future Metrics)

| Metric | Definition |
|--------|------------|
| **Knowledge Growth** | New validated entries / time |
| **Learning Velocity** | Trust recalibration rate + archive/promote throughput |
| **False Decision Rate** | High-conviction labels that underperformed baseline |
| **Validation Success Rate** | Candidates passing full pipeline |
| **Trust Distribution** | Spread of organism trust scores (avoid single-organism dominance) |
| **Organism Stability** | Output variance, error rate, pipeline uptime |
| **Research Quality** | Explainability coverage, dossier completeness |
| **Production Candidate Count** | Human-review queue size (cap for safety) |

These metrics feed dashboards and sprint planning — not live risk engines in TAE 1.0.

---

## 8. Layer Boundaries (Hard Rules)

| Layer | May do | May not do |
|-------|--------|------------|
| Market | Download, enrich, normalize | Place orders |
| Organism | Observe, score, explain | Connect broker |
| Knowledge Core | Store, query, lineage | Auto-trade |
| Collective Intelligence | Fuse, consensus | Execute |
| Evolution | Trust, archive, promote (research) | Modify `live_bot.py` |
| Future Paper/Broker | Paper sim (TAE 4+) | Live without gate (TAE 5+) |

---

## 9. File & Module Map (Current → TAE)

| TAE concept | Current artifact |
|-------------|------------------|
| Discovery | `edge_discovery_engine_v30.py`, `research_core/` |
| Ensemble | `edge_ensemble_engine_v31.py` |
| Evidence | `evidence_engine_v40.py` |
| Framework | `research_core/` package |
| Context | `context_intelligence_research_v18.py` |
| Momentum | `momentum_continuation_research_v11.py` |

---

## Related Documents

- `TAE_VISION.md` — philosophy and motto
- `TAE_ORGANISM_CONTRACT.md` — organism obligations
- `TAE_KNOWLEDGE_CORE_SPEC.md` — storage and trust model
- `TAE_ROADMAP.md` — version phases 1.0–5.0

---

*RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION*
