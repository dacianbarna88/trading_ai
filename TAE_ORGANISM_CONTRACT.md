# TAE Organism Contract

**Trading AI Ecosystem — Universal Organism Specification**

Every organism in TAE is a **research agent** with obligations — not an autonomous trader.

Version: Foundation Sprint 1  
Status: RESEARCH_ONLY | NO_BROKER | NO_EXECUTION

---

## Purpose

This contract ensures:

- **Modularity** — organisms can be added, replaced, or archived independently
- **Auditability** — every conclusion has a traceable explanation
- **Collective intelligence** — outputs are composable evidence packets
- **Evolution** — organisms report what they learned, not just what they scored

An organism that cannot answer all seven questions completely is **not TAE-compliant**.

---

## The Seven Questions

### 1. What do you observe?

**Requirement:** Declare the raw sensory scope.

| Must include | Example (Context Organism) |
|--------------|----------------------------|
| Data sources | SPY OHLCV, ticker OHLCV, sector map |
| Feature domains | Regime, SMA distances, SPY returns |
| Temporal scope | Signal date, 10y history window |
| Universe | `us_expanded_universe.txt` |
| Frequency | Per-signal, per-ticker |

**Anti-pattern:** "I look at the market" without naming inputs.

---

### 2. What do you understand?

**Requirement:** State the **interpretation model** — rules, bins, patterns, or hypotheses applied to observations.

| Must include | Example (Evidence Organism) |
|--------------|----------------------------|
| Model type | Weighted category scoring |
| Key thresholds | Decision labels 40/60/80 |
| Dependencies | Ensemble scores, bucket stats |
| Assumptions | BEAR regime favored by survivor edges |

**Anti-pattern:** Scores with no documented logic.

---

### 3. What evidence do you produce?

**Requirement:** Enumerate **concrete artifacts** — files, records, packet fields.

| Artifact type | Examples |
|---------------|----------|
| CSV outputs | `evidence_signal_dossiers.csv` |
| Summaries | `evidence_engine_summary.txt` |
| Structured packets | `EvidencePacket` JSON rows |
| Metrics | Win rate, PF, lift vs baseline |

**Minimum:** At least one persistent artifact per run plus per-entity records (e.g., per signal).

---

### 4. How confident are you?

**Requirement:** Provide **calibrated confidence** separate from raw score.

| Field | Meaning |
|-------|---------|
| `confidence` | 0–100 belief in this specific conclusion |
| `sample_depth` | Trades, signals, or windows used |
| `validation_tier` | DISCOVERY / VALIDATED / ARCHIVED |
| `uncertainty_flags` | Low sample, concentration, WF failure |

Confidence must **degrade** when sample size is thin or validation failed — not inflate with optimism.

---

### 5. How do you explain your conclusion?

**Requirement:** Human-readable explanation for every scored entity.

| Standard | Implementation |
|----------|----------------|
| Plain language | No opaque model IDs without description |
| Causal framing | "Because regime is BEAR and edges favor…" |
| Caveats | Conflicts, missing data, warnings |
| RESEARCH banner | No implied production approval |

Evidence Organism example:

> *Market Context: Score 92, STRONG_SUPPORT — Signal occurred during BEAR regime where discovered edges historically outperformed baseline.*

---

### 6. What did you learn?

**Requirement:** Post-run **learning summary** depositable to Knowledge Core.

| Learning type | Example |
|---------------|---------|
| Confirmatory | HIGH_CONVICTION bucket beat baseline by 6% avg |
| Refutatory | BULL regime packets conflict with survivor edges |
| Operational | SMA20 enrichment required for rule matching |
| Meta | Monotonicity positive across ensemble buckets |

Empty learning ("nothing new") is valid only when explicitly justified.

---

### 7. How do you help the ecosystem?

**Requirement:** Declare **downstream consumers** and contribution type.

| Contribution | Consumer |
|--------------|----------|
| Edge candidates | Ensemble Organism |
| Consensus scores | Evidence Organism |
| Dossiers | Decision Organism (future paper) |
| Archive proposals | Evolution Layer |
| Gap detection | Ecosystem Health |

Every organism must name at least one other organism or layer it feeds.

---

## Evidence Packet Schema (Required Output)

All organisms SHOULD emit packets compatible with Collective Intelligence:

```yaml
packet_id: string          # unique, deterministic where possible
organism_id: string        # e.g. context_organism
organism_version: string   # e.g. 1.8
timestamp: ISO-8601
scope:
  ticker: string
  signal_date: date
  signal_id: string        # optional hash
scores:
  evidence_score: 0-100
  confidence: 0-100
  trust: 0-100             # organism historical trust
status: string             # STRONG_SUPPORT | SUPPORT | NEUTRAL | WARNING | STRONG_WARNING
explanation: string        # human-readable
artifacts:
  - path: string
  - type: csv | txt | json
learning:
  summary: string
  tags: [string]
```

---

## Lifecycle States

| State | Meaning |
|-------|---------|
| `DRAFT` | Experimental, not wired to consensus |
| `ACTIVE` | Produces packets consumed by CI layer |
| `DEPRECATED` | Superseded; outputs ignored but archived |
| `SUSPENDED` | Health failure; requires human review |

---

## Compliance Checklist

Before an organism is registered in TAE:

- [ ] Answers all seven questions in module README or spec section
- [ ] Produces at least one auditable artifact per run
- [ ] Explanations are human-readable
- [ ] Confidence degrades under weak samples
- [ ] Learning summary written to run output or Knowledge Core
- [ ] No broker imports, no order creation
- [ ] Tagged `RESEARCH_ONLY | NO_BROKER | NO_EXECUTION`

---

## Organism Registry (Sprint 1)

| Organism | Version hint | Contract status |
|----------|--------------|-----------------|
| Context | V1.8 | Precursor — partial packet schema |
| Momentum | V1.1–V1.3 | Precursor — baseline provider |
| Liquidity | V1.7 | Precursor |
| Recovery | V1.5 | Precursor |
| Volatility | Feature bins | Embedded in discovery |
| Risk | V1.4, V1.9 | Precursor |
| Evidence | V4.0 | **First full dossier contract** |
| Learning | V1.6 | Meta-analysis precursor |
| Memory | — | Spec only (`TAE_KNOWLEDGE_CORE_SPEC.md`) |
| Decision | V3.1 + V4.0 | Ensemble + evidence labels |

Formal registration into a `OrganismRegistry` is a TAE 2.0 deliverable.

---

## Violations

The following **void compliance**:

- Connecting to a broker or creating orders
- Auto-promoting to production without human gate
- Black-box scores without explanation
- Modifying live execution paths (`live_bot.py`, `dashboard_v2.py`, `portfolio.csv`)
- Silent failure without audit log

---

## Related Documents

- `TAE_ARCHITECTURE.md` — where organisms sit in the stack
- `TAE_KNOWLEDGE_CORE_SPEC.md` — how learning is stored
- `TAE_VISION.md` — why organisms exist

---

*RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION*
