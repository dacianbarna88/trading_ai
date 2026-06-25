# TAE Knowledge Core Specification

**Trading AI Ecosystem — Knowledge Storage & Trust Model**

Version: Foundation Sprint 1  
Status: RESEARCH_ONLY | NO_BROKER | NO_EXECUTION

---

## Purpose

The Knowledge Core is TAE's **durable memory**. It is not a database of trades — it is a registry of **what the ecosystem believes, why, how strongly, and under what conditions those beliefs hold or fail**.

Without the Knowledge Core, organisms produce ephemeral CSVs. With it, TAE becomes cumulative intelligence.

---

## Design Principles

1. **Evidence is immutable** — raw run outputs are never silently overwritten; new runs append lineage.
2. **Trust is earned** — promotion increases trust; false decisions decrease it.
3. **Status is explicit** — every pattern has a lifecycle state, never implicit approval.
4. **Failure conditions are mandatory** — knowing when an edge fails is as valuable as knowing when it works.
5. **Explainability is stored** — explanations are queryable fields, not log file scraps.
6. **No execution hooks** — Knowledge Core never triggers orders.

---

## Entity Model

### 1. Pattern (Validated Edge)

A **Pattern** is a research-validated rule or conjunction discovered by the Discovery Engine or equivalent.

| Field | Type | Description |
|-------|------|-------------|
| `pattern_id` | string | Stable ID (e.g., Rule_ID from V3.0) |
| `description` | string | Human-readable rule text |
| `bin_columns` | list | Feature conjunction |
| `family` | enum | Market Regime, Trend, RSI, etc. |
| `status` | enum | See Status Model |
| `trust_score` | 0–100 | Evolution-adjusted reliability |
| `confidence_score` | 0–100 | Latest validation confidence |
| `metrics` | object | Trades, win rate, avg return, PF |
| `validation` | object | WF pass rate, robustness score |
| `success_conditions` | list | When edge works (e.g., BEAR regime) |
| `failure_conditions` | list | When edge fails (e.g., BULL + high RSI) |
| `created_at` | timestamp | First discovery |
| `updated_at` | timestamp | Last validation |
| `lineage` | list | Run IDs that touched this pattern |

**Source today:** `edge_discovery_survivors.csv` → import as `VALIDATED` proposals.

---

### 2. Evidence Record

An **Evidence Record** is a per-signal dossier from the Evidence Organism (or any organism producing dossiers).

| Field | Type | Description |
|-------|------|-------------|
| `evidence_id` | string | Hash(ticker, signal_date, run_id) |
| `ticker` | string | |
| `signal_date` | date | |
| `organism_id` | string | e.g., evidence_organism_v4 |
| `categories` | object | 8 category scores + statuses + explanations |
| `overall_score` | 0–100 | Weighted evidence score |
| `decision_label` | enum | IGNORE / WATCH / PAPER_CANDIDATE / HIGH_CONVICTION |
| `forward_return_60d` | float | Outcome (research label) |
| `consensus_score` | float | From ensemble layer |
| `explanation_summary` | string | Top-line narrative |
| `run_id` | string | Provenance |

**Source today:** `evidence_signal_dossiers.csv`.

---

### 3. Confidence Object

Confidence is **per conclusion**, not global.

```json
{
  "score": 86.91,
  "components": {
    "robustness": 76.21,
    "walk_forward": 85.71,
    "sample_depth": 355,
    "sector_diversity": 9
  },
  "tier": "VALIDATED",
  "degradation_reasons": []
}
```

Rules:

- `sample_depth < 100` → cap confidence at 70 unless explicitly waived
- WF pass rate < 50% → tier cannot be `VALIDATED`
- Concentration flags → attach `degradation_reasons`

---

### 4. Trust Object

Trust is **per organism or per pattern**, updated by Evolution Layer.

| Field | Description |
|-------|-------------|
| `entity_id` | organism_id or pattern_id |
| `trust_score` | 0–100 |
| `history` | List of {date, delta, reason} |
| `false_decision_count` | High-conviction misses |
| `validation_success_rate` | Promotions / attempts |

Initial trust: 50 (neutral). Range clamped [0, 100].

---

### 5. Status Model

| Status | Meaning | May feed consensus? |
|--------|---------|-------------------|
| `DISCOVERY` | New candidate, minimal validation | Yes, low weight |
| `VALIDATED` | Passed full pipeline | Yes, full weight |
| `PRODUCTION_CANDIDATE` | Human review queue | Yes, flagged |
| `ARCHIVED` | Weak or refuted | No |
| `SUSPENDED` | Data or logic failure | No |

**Promotion path:** `DISCOVERY` → `VALIDATED` → `PRODUCTION_CANDIDATE` (human only)  
**Demotion path:** any → `ARCHIVED` on validation failure or trust collapse

---

### 6. History & Lineage

Every Knowledge Core mutation records:

```json
{
  "event_id": "uuid",
  "event_type": "PROMOTE | ARCHIVE | TRUST_UPDATE | IMPORT",
  "entity_type": "pattern | evidence | organism",
  "entity_id": "string",
  "actor": "organism_id | human | evolution_layer",
  "timestamp": "ISO-8601",
  "before": {},
  "after": {},
  "reason": "string"
}
```

Enables audit: *"Why was this edge archived on 2026-06-24?"*

---

### 7. Evolution Log

Tracks ecosystem learning events:

| Event | Trigger |
|-------|---------|
| `EDGE_PROMOTED` | Survivor passes ensemble + evidence |
| `EDGE_ARCHIVED` | WF failure, trust below threshold |
| `WEIGHT_RECALIBRATED` | Bucket performance drift |
| `ORGANISM_TRUST_UPDATED` | Predictive accuracy change |
| `MISSING_ORGANISM_FLAGGED` | Health metric gap |

---

### 8. Condition Registry

Dedicated store for **when edges work / fail**:

```json
{
  "pattern_id": "P_S_BIN_Regime_BEAR_...",
  "works_when": [
    "Market_Regime == BEAR",
    "SPY below SMA200",
    "Sample depth >= 100"
  ],
  "fails_when": [
    "Market_Regime == BULL",
    "RSI > 70",
    "Top ticker concentration > 35%"
  ],
  "source": "robustness_validator + evidence conflicts"
}
```

Populated from robustness issues, conflict evidence, and bucket backtests.

---

## Storage Architecture (Phased)

### Sprint 1 (Documentation + file-based)

| Store | Format | Location |
|-------|--------|----------|
| Patterns | CSV import | `edge_discovery_survivors.csv` |
| Evidence | CSV | `evidence_signal_dossiers.csv` |
| Ensemble stats | CSV | `edge_ensemble_bucket_stats.csv` |
| Summaries | TXT | `*_summary.txt` |
| Lineage | TXT logs | `edge_discovery_runtime_log.txt` |

### TAE 2.0 (Knowledge Core v1)

- SQLite or JSONL canonical store under `tae_knowledge/`
- Import adapters from existing CSV outputs
- Query API: `get_pattern()`, `get_evidence()`, `get_trust()`

### TAE 3.0+

- Versioned pattern graph
- Cross-run diff and trust timelines
- Organism packet ingestion bus

---

## Write Protocol

1. Organism completes run → writes artifacts to disk
2. **Import adapter** maps artifacts to Knowledge Core entities
3. Validation layer checks schema compliance
4. Evolution Layer applies trust deltas (if outcomes known)
5. History event appended — never silent merge

**No organism writes directly to production execution config.**

---

## Read Protocol

| Consumer | Reads |
|----------|-------|
| Ensemble Organism | VALIDATED patterns |
| Evidence Organism | Patterns + ensemble scores + bucket stats |
| Decision Organism | Evidence records + trust |
| Evolution Layer | Outcomes vs labels |
| Human researcher | Summaries + dossiers + lineage |
| Future paper system | HIGH_CONVICTION records with full explanation |

---

## Query Examples (Future API)

```
GET /patterns?status=VALIDATED&family=Market Regime
GET /evidence?ticker=AAPL&min_score=80
GET /trust/organism/evidence_organism_v4
GET /conditions/pattern/{id}/failure
GET /history?entity_id=P_S_BIN_Regime_BEAR
```

---

## Data Quality Gates

| Gate | Rule |
|------|------|
| Completeness | Dossier must have all 8 categories |
| Explainability | No null `explanation` on scored entities |
| Provenance | Every record has `run_id` |
| Safety | No field named `order`, `broker`, `execute` |
| Immutability | Historical runs preserved, not replaced |

---

## Relationship to `research_core`

| research_core module | Knowledge Core role |
|----------------------|---------------------|
| `DiscoveryConfig` | Pattern discovery thresholds |
| `EvaluationResult` | Pattern metrics template |
| `RunResult` | Run lineage prototype |
| `AuditEntry` | History event prototype |
| Evidence / Ensemble outputs | Import sources |

Memory Organism (future) implements this spec as code.

---

## Related Documents

- `TAE_ARCHITECTURE.md` — Knowledge Core in system context
- `TAE_ORGANISM_CONTRACT.md` — what organisms deposit
- `TAE_ROADMAP.md` — when Memory Organism ships

---

*RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION*
