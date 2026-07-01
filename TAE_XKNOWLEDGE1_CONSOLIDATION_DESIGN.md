# TAE X.KNOWLEDGE-1 — Consolidation Layer Design

**Date:** 2026-07-01  
**Status:** DESIGN ONLY — no implementation  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Verdict:** **BUILD AS CONSOLIDATION LAYER / DO NOT BUILD GREENFIELD**

---

## Executive summary

Pre-build audit confirmed TAE already has multiple overlapping knowledge, evidence, discovery, and learning subsystems spread across `research_core/` and root-level JSON artifacts. X.KNOWLEDGE-1 must **not** add another parallel registry. It must be a **read-only consolidation layer** that:

1. Reads existing authoritative artifacts (no rewrite of upstream engines).
2. Normalizes all findings into a single canonical pattern schema.
3. Writes three downstream outputs: `tae_knowledge_base.json`, `tae_knowledge_base.md`, `tae_knowledge_summary.md`.
4. Feeds ecosystem review, unified runtime, dashboard, and committee — **research context only**, never BUY/SELL.

---

## 1. Existing source inventory

### A. Core libraries (`research_core/`)

| Source | Path | Role today | Persistence |
|--------|------|------------|-------------|
| **Knowledge Core** | `research_core/ecosystem/knowledge_core.py` | In-memory validated pattern registry (`KnowledgePattern`, `PatternStatus`) | **In-memory only** (Sprint 2 note) |
| **Knowledge Graph** | `research_core/ecosystem/knowledge_graph.py` | Graph relationships between knowledge entities | In-memory / demo |
| **Memory Layer** | `research_core/ecosystem/memory_layer.py` | Ecosystem memory abstraction | Runtime |
| **Organism Memory** | `research_core/ecosystem/organism_memory.py` | Organism-level memory | JSON (`tae_organism_memory.json`) |
| **Evidence Packet** | `research_core/ecosystem/evidence_packet.py` | Packet contract for evidence → knowledge linkage | Event stream |
| **Discovery Registry** | `research_core/discovery/discovery_registry.py` | Persistent discovery store | `tae_discoveries.json` |
| **Discovery Model** | `research_core/discovery/discovery_model.py` | `Discovery` dataclass + statuses | Via registry |
| **Evidence Engine** | `research_core/evidence_engine/*` | Registry, gap registration, dependency map | Multiple JSON reports |
| **Evidence History** | `research_core/evidence_history/*` | Accumulator + record model | `tae_evidence_history.json` |
| **Learning Engine** | `research_core/learning/learning_engine.py` | Learning report generation | Via runtime |
| **Learning Memory** | `research_core/runtime/learning_memory.py` | Runtime learning memory adapter | `tae_runtime_learning_memory.json` |
| **Knowledge Integration** | `research_core/integration/knowledge_integration.py` | Phase V integration glue | Demo/runtime |
| **Knowledge Candidate** | `research_core/hypothesis/knowledge_candidate.py` | Hypothesis → knowledge candidate promotion | `tae_knowledge_candidates.json` |

### B. Root-level engines & artifacts

| Source | Path | Role today |
|--------|------|------------|
| **Evidence report (SSOT for evidence)** | `tae_evidence_engine_report.json` | Canonical evidence aggregation; 7 confirmed items; gap + confidence registration |
| **Runtime learning memory** | `tae_runtime_learning_memory.json` | Strategy tracking, promotion review, conflict warnings |
| **Knowledge candidates** | `tae_knowledge_candidates.json` | 3 promoted research candidates (`kn_s53_*`, `kn_d5_*`) |
| **Strategy discovery** | `tae_strategy_discovery.json` | Hypothesis/candidate counts (referenced by ecosystem review) |
| **Discovery hypothesis rankings** | `tae_discovery_hypothesis_rankings.json` | Ranked discovery hypotheses |
| **Learning report / runtime** | `tae_learning_report.json`, `tae_learning_runtime.json` | Learning pipeline outputs |
| **Pattern discovery (legacy root)** | `pattern_discovery_engine.py` | Older pattern discovery engine |
| **Learning memory CSV** | `learning_memory.csv` | Tabular learning history |
| **Historical memory** | `historical_memory.csv`, `historical_patterns.csv` | Historical pattern/memory stores |

### C. Intraday fade stack (newest, well-scoped)

| Source | Path | Role today |
|--------|------|------------|
| **Fade history recorder** | `tae_intraday_fade_history.py` | Appends CSV/JSON daily observations |
| **History data** | `runtime_outputs/tae_intraday_fade_history.csv/json` | Persistent intraday observations |
| **Daily summaries** | `runtime_outputs/tae_intraday_fade_daily_summary.json` | Per-run portfolio totals |
| **Discovery engine** | `tae_intraday_discovery_engine.py` | Pattern discovery from fade history |
| **Discovery output** | `tae_intraday_discovery_engine.json` | Ticker/classification/daily learning + patterns |

### D. Downstream consumers (today)

| Consumer | What it reads |
|----------|---------------|
| `tae_full_ecosystem_review.py` | `tae_evidence_engine_report.json`, `tae_strategy_discovery.json`, meta/ranking/advisory JSON |
| `tae_unified_runtime.py` | Delegates to `unified_runtime_builder` — ticker SSOT, no knowledge merge yet |
| Dashboard | Various runtime summaries under `runtime_outputs/*learning*_summary.txt` |

---

## 2. Recommended SSOT

### Principle: **Read-many, write-one**

X.KNOWLEDGE-1 does **not** replace upstream SSOTs. Each domain keeps its canonical writer:

| Domain | Upstream SSOT (writer) | Consolidation read-only |
|--------|------------------------|-------------------------|
| Evidence | `tae_evidence_engine_report.json` | Yes |
| Strategy learning | `tae_runtime_learning_memory.json` | Yes |
| Knowledge candidates | `tae_knowledge_candidates.json` | Yes |
| Research discoveries | `tae_discoveries.json` via `DiscoveryRegistry` | Yes |
| Intraday fade patterns | `tae_intraday_discovery_engine.json` | Yes |
| Intraday observations | `runtime_outputs/tae_intraday_fade_history.json` | Yes (metadata only) |
| In-memory KnowledgeCore | `knowledge_core.py` | **No direct read** until persisted export exists |

### Consolidation SSOT (new, write-only by X.KNOWLEDGE-1)

| Artifact | Role |
|----------|------|
| **`tae_knowledge_base.json`** | **Canonical merged view** — normalized patterns, statuses, confidence, evolution, provenance |
| `tae_knowledge_base.md` | Full human-readable catalog |
| `tae_knowledge_summary.md` | Executive summary for review/dashboard |

**Rule:** Downstream systems (ecosystem review, dashboard, committee) should prefer `tae_knowledge_base.json` over reading 10+ source files individually — but upstream engines remain authoritative for their domain.

---

## 3. Normalized pattern schema

Every upstream finding maps to one **`KnowledgeBaseEntry`**:

```json
{
  "entry_id": "kb_intraday_P001_PM",
  "fingerprint": "sha256-prefix",
  "source_system": "intraday_discovery | discovery_registry | evidence_engine | learning_memory | knowledge_candidates",
  "source_ref": "original id / path",
  "pattern_type": "REPEATED_SIGNIFICANT_FADE | HIGH_FADE_TICKER | ... | EVIDENCE_CONFIRMED | LEARNING_TRACKING | DISCOVERY_NEW",
  "scope": "ticker | portfolio | dataset | strategy | evidence",
  "subject": "PM | kn_d5_00002 | accounting_verified | ...",
  "title": "Human-readable title",
  "description": "What was observed",
  "status": "EXPERIMENTAL | LEARNING | CONFIRMED | RETIRED",
  "confidence": "LOW | MEDIUM | HIGH",
  "confidence_score": 0.0,
  "evolution_state": "new | repeated | strengthening | weakening | retired",
  "observations": 14,
  "metrics": { "missed_opportunity_usd": 129.84, "...": "..." },
  "recommendation": "PRIORITIZE_TRACKING | TEST_TRAILING_SHADOW | ...",
  "safety_mode": "SHADOW_ONLY",
  "live_trading_impact": "NONE",
  "first_seen_at": "ISO8601",
  "last_seen_at": "ISO8601",
  "provenance": ["tae_intraday_discovery_engine.json#patterns[0]"]
}
```

### 3.1 Intraday discovery → normalized

**Input:** `tae_intraday_discovery_engine.json` → `patterns[]`, `ticker_learning[]`, `recommendations[]`

| Upstream field | Normalized mapping |
|----------------|-------------------|
| `pattern_type` | `pattern_type` (preserve) |
| `subject` | `subject` |
| `observations` | `observations` |
| `confidence` (LOW/MEDIUM/HIGH) | `confidence` |
| `value`, `metric` | `metrics.{metric}` |
| `recommendation` | `recommendation` |
| `dataset_health.minimum_sample_warning` | Forces `status=EXPERIMENTAL`, caps confidence at LOW |

**Initial status mapping:**

- `LOW_CONFIDENCE_INSUFFICIENT_SAMPLE` → `EXPERIMENTAL`
- `REPEATED_SIGNIFICANT_FADE`, `HIGH_FADE_TICKER` → `LEARNING`
- Shadow strategy patterns (`BEST_SHADOW_*`) → `LEARNING` (research hypothesis, not confirmed edge)

### 3.2 Discovery registry → normalized

**Input:** `tae_discoveries.json` via `DiscoveryRegistry.list_all()`

| DiscoveryStatus (upstream) | Consolidation status |
|----------------------------|---------------------|
| `NEW`, `UNDER_REVIEW` | `EXPERIMENTAL` |
| `LINKED`, `CONVERTED` | `LEARNING` |
| `VALIDATED` | `CONFIRMED` |
| `DISMISSED`, `ARCHIVED` | `RETIRED` |

| Upstream field | Normalized mapping |
|----------------|-------------------|
| `discovery_id` | `source_ref`, `entry_id` prefix `kb_disc_*` |
| `confidence` (0–100 float) | `confidence_score`; map ≥70→HIGH, 40–69→MEDIUM, <40→LOW |
| `category`, `title` | `pattern_type`, `title` |
| `fingerprint` | dedupe key |

### 3.3 Evidence engine → normalized

**Input:** `tae_evidence_engine_report.json` → `evidence_items[]`

| Upstream `status` | Consolidation status |
|-------------------|---------------------|
| `CONFIRMED` | `CONFIRMED` |
| `INCONCLUSIVE` | `LEARNING` |
| `REJECTED` | `RETIRED` |

| Upstream field | Normalized mapping |
|----------------|-------------------|
| `evidence_id` | `source_ref`, `entry_id` prefix `kb_ev_*` |
| `conclusion`, `title` | `description`, `title` |
| `risk_level` | metadata; does not override confidence tier |
| Report-level `confirmed_count` | Dataset health metric |

Evidence items are **portfolio/system scope**, not ticker-specific unless `source_ref` implies otherwise.

### 3.4 Learning memory → normalized

**Input:** `tae_runtime_learning_memory.json`

| Upstream concept | Normalized mapping |
|------------------|-------------------|
| `top_ranked_strategy` | entry scope `strategy`, `status=LEARNING` or `CONFIRMED` based on tracking |
| `paper_tracking_needs[]` | One entry per candidate; `sample_insufficient=true` → `EXPERIMENTAL` |
| `conflict_warnings[]` | entries scope `system`, `pattern_type=LEARNING_CONFLICT`, `status=LEARNING` |
| `promotion_review_candidate` | if null → no CONFIRMED promotion |

| Tracking status | Consolidation status |
|-----------------|---------------------|
| `TRACKING_ACTIVE`, trades below threshold | `LEARNING` |
| `BLOCKED`, `sample_insufficient` | `EXPERIMENTAL` |
| Promotion approved (future) | `CONFIRMED` — **not auto-promoted by consolidation** |

### 3.5 Knowledge candidates → normalized

**Input:** `tae_knowledge_candidates.json` → `candidates[]`

| Upstream `status` | Consolidation status |
|-------------------|---------------------|
| `CANDIDATE` | `LEARNING` |
| Promoted (future upstream) | `CONFIRMED` |
| Rejected/archived | `RETIRED` |

Map `quality_score`, `sample_size`, `robustness_label` into `metrics` and derive confidence from sample_size thresholds (see §5).

### Dedupe rule

Entries dedupe on `(source_system, fingerprint)` or `(source_system, source_ref)`. On collision, merge `provenance[]`, update `last_seen_at`, recompute evolution (§6).

---

## 4. Status semantics

| Status | Meaning | Live impact |
|--------|---------|-------------|
| **EXPERIMENTAL** | First observation or insufficient sample; hypothesis only | **NONE** — do not act |
| **LEARNING** | Repeated signal accumulating; shadow testing recommended | **NONE** — track in paper/shadow |
| **CONFIRMED** | Upstream evidence engine or validated discovery confirms | **NONE** — research confidence only; still no auto-execution |
| **RETIRED** | Dismissed, rejected, archived, or contradicted | **NONE** — historical record |

**Mapping note:** Consolidation **never upgrades** intraday fade patterns to `CONFIRMED` until X.KNOWLEDGE-1B evolution rules + evidence linkage criteria are met. Evidence engine `CONFIRMED` passes through as `CONFIRMED`.

---

## 5. Confidence semantics

| Tier | Criteria (consolidation layer) |
|------|--------------------------------|
| **LOW** | observations < 10; OR intraday `minimum_sample_warning`; OR upstream confidence < 40; OR `sample_insufficient=true` |
| **MEDIUM** | observations 10–29; OR upstream confidence 40–69; OR 2+ consistent observations without contradiction |
| **HIGH** | observations ≥ 30; OR upstream evidence `CONFIRMED`; OR discovery `VALIDATED` with sample_size ≥ 500 |

**confidence_score:** Normalized 0.0–1.0 for sorting:

```
score = weighted(observation_count, upstream_confidence, data_quality, recency_decay)
```

Intraday patterns today (14 obs, 2 days) → **all LOW** regardless of local pattern confidence field.

---

## 6. Pattern evolution lifecycle

| Evolution state | Trigger |
|-----------------|---------|
| **new** | First time entry appears in consolidation run |
| **repeated** | Same fingerprint seen again; metrics stable (±10%) |
| **strengthening** | observations ↑; confidence tier unchanged or upgraded; metric magnitude ↑ |
| **weakening** | observations flat but metric magnitude ↓ >20%; or confidence tier downgraded |
| **retired** | upstream status → DISMISSED/REJECTED/ARCHIVED; or 30 days absent from source |

Evolution is computed by comparing current consolidation run to previous `tae_knowledge_base.json` (if exists). X.KNOWLEDGE-1A may skip evolution (all `new`); X.KNOWLEDGE-1B implements diff.

---

## 7. Required outputs

### `tae_knowledge_base.json`

```json
{
  "schema": "tae_knowledge_base",
  "version": 1,
  "mode": "SHADOW_ONLY",
  "live_trading_impact": "NONE",
  "generated_at": "ISO8601",
  "ssot_note": "Read-only consolidation; upstream artifacts remain authoritative",
  "dataset_health": {
    "source_count": 5,
    "entries_total": 42,
    "by_status": {},
    "by_confidence": {},
    "by_source_system": {}
  },
  "entries": [ "KnowledgeBaseEntry[]" ],
  "recommendations": [ "SHADOW_ONLY research recommendations" ],
  "sources_loaded": { "tae_evidence_engine_report.json": true, "...": false }
}
```

### `tae_knowledge_base.md`

- Catalog grouped by `source_system` then `status`
- Table per entry: id, subject, pattern_type, status, confidence, evolution, recommendation
- Provenance links to upstream files

### `tae_knowledge_summary.md`

- Top 10 entries by confidence_score
- Count by status / confidence / source
- Active patterns requiring tracking (LEARNING + PRIORITIZE_*)
- Retired / contradicted count
- Explicit banner: **NO BUY/SELL — RESEARCH ONLY**

---

## 8. Future integration points

### 8.1 `tae_full_ecosystem_review.py`

Add section **`I_knowledge_base`** (read-only):

- Load `tae_knowledge_base.json`
- Surface: `entries_total`, `by_status`, top LEARNING patterns, intraday fade count
- Extend `_learning_section()` or parallel section — **do not duplicate evidence parsing**
- Feed `_final_verdict()` with `knowledge_maturity`: `INSUFFICIENT | ACCUMULATING | DIVERSE`

### 8.2 `tae_unified_runtime.py` / `unified_runtime_builder`

- Optional per-ticker `knowledge_context[]` array: intraday fade entries where `scope=ticker`
- **Read-only enrichment** — no score changes to BUY logic
- Link by ticker symbol match

### 8.3 Dashboard

New panel: **Knowledge Base (Shadow)**

- Summary from `tae_knowledge_summary.md`
- Filters: status, confidence, source_system
- Drill-down to `tae_knowledge_base.md`

### 8.4 Committee (SHADOW only)

- Committee receives knowledge entries as **research briefs**, not votes
- Format: pattern_type + confidence + recommendation
- Explicit guard: committee output tagged `SHADOW_RESEARCH — NO_EXECUTION`

---

## 9. Explicit non-goals

| Do NOT | Reason |
|--------|--------|
| Duplicate `KnowledgeCore` in-memory registry | Use read + optional future sync adapter |
| Rewrite `DiscoveryRegistry` | Read `tae_discoveries.json` |
| Modify `live_bot.py` | Execution boundary |
| Generate BUY/SELL signals | Research layer only |
| Change STOP/TP/Risk/Broker/Trailing | Out of scope |
| Modify Market Data Layer | Out of scope |
| Write back to upstream SSOTs in 1A | Read-only aggregator first |
| Auto-promote intraday patterns to live | Requires X.INTRADAY-3+ and explicit sprint |

---

## 10. Phased implementation plan

### X.KNOWLEDGE-1A — Read-only aggregator

**Deliverables:**

- `tae_knowledge_base.py` (new module)
- `tae_knowledge_base_test.py`
- Outputs: `tae_knowledge_base.json`, `.md`, summary `.md`

**Scope:**

- Load all source JSON files (graceful missing-file handling)
- Normalize to `KnowledgeBaseEntry`
- Dedupe by fingerprint/source_ref
- Assign status/confidence per §4–§5
- All entries `evolution_state=new` (no diff yet)

### X.KNOWLEDGE-1B — Confidence evolution

**Scope:**

- Load previous `tae_knowledge_base.json`
- Compute evolution states (§6)
- Observation count aggregation across runs for intraday ticker patterns
- Confidence tier upgrades when thresholds crossed
- Emit `evolution_changelog` in JSON

### X.KNOWLEDGE-1C — Ecosystem review integration

**Scope:**

- `tae_full_ecosystem_review.py`: add `I_knowledge_base` section
- Include intraday discovery in `learning_progress` heuristic
- Cross-reference evidence contradictions vs knowledge entries

### X.KNOWLEDGE-1D — Dashboard panel

**Scope:**

- Panel in command center dashboard
- Read `tae_knowledge_summary.md` or JSON directly
- SHADOW badge on all rows

---

## 11. Required tests

| Test | Validates |
|------|-----------|
| `test_load_missing_sources_graceful` | Partial sources → valid base with `sources_loaded` flags |
| `test_normalize_intraday_pattern` | Discovery pattern → `KnowledgeBaseEntry` |
| `test_normalize_evidence_item` | CONFIRMED evidence → status CONFIRMED |
| `test_normalize_discovery_registry` | DiscoveryStatus mapping |
| `test_normalize_learning_memory` | Tracking blocked → EXPERIMENTAL |
| `test_dedupe_fingerprint` | Same pattern twice → one entry, merged provenance |
| `test_confidence_low_insufficient_sample` | 14 obs → LOW |
| `test_status_never_confirms_intraday_without_evidence` | Intraday only → max LEARNING |
| `test_json_md_output_written` | Schema + required keys |
| `test_no_buy_sell_language` | Recommendations ⊆ allowed SHADOW set |
| `test_evolution_diff` (1B) | strengthening/weakening detection |
| `test_ecosystem_section_shape` (1C) | Review JSON includes knowledge section |

---

## 12. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Fragmented SSOT** — 10+ JSON sources with different schemas | High | Single consolidation output; `sources_loaded` transparency |
| **Status drift** — upstream changes without consolidation rerun | Medium | Timestamp + stale warning if `generated_at` older than 24h |
| **Over-confident intraday patterns** — 14 obs treated as signal | High | Hard cap intraday at LEARNING/LOW until 30+ obs |
| **KnowledgeCore in-memory not persisted** | Medium | 1A reads JSON only; future adapter exports KnowledgeCore → JSON |
| **Duplicate pattern IDs** across systems | Medium | Fingerprint dedupe + prefixed `entry_id` |
| **Ecosystem review bloat** | Low | Summary section only in 1C; full catalog stays in knowledge base |
| **Accidental execution linkage** | Critical | `live_trading_impact: NONE` on every entry; no live_bot import |
| **Conflict with evidence engine precedence** | Medium | Evidence CONFIRMED wins over intraday LEARNING for same subject |

---

## 13. Final verdict

### BUILD AS CONSOLIDATION LAYER — DO NOT BUILD GREENFIELD

X.KNOWLEDGE-1 is justified as a **thin, read-only aggregation module** that:

1. Respects existing upstream writers (`evidence_engine`, `DiscoveryRegistry`, `intraday_discovery`, `learning_memory`, `knowledge_candidates`).
2. Produces one canonical read surface (`tae_knowledge_base.json`) for humans and downstream TAE systems.
3. Stays SHADOW/PAPER with zero broker or live_bot coupling.
4. Defers execution-adjacent work to X.INTRADAY-3 (Profit Protection Advisory) and future explicit promotion sprints.

**Do not** implement a new pattern registry, new evidence engine, or new discovery pipeline.

**Do** implement `tae_knowledge_base.py` as specified in phase 1A when approved.

---

*TAE X.KNOWLEDGE-1 — consolidation design. Design doc only; no code changes.*
