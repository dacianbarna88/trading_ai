# TAE X.KNOWLEDGE-1A — Read-only Knowledge Aggregator Report

**Date:** 2026-07-01  
**Sprint:** X.KNOWLEDGE-1A  
**Mode:** SHADOW_ONLY / PAPER_ONLY / NO_BROKER  
**Design reference:** `7927429` — TAE knowledge: add consolidation design

---

## 1. Objective

Implement the first **Knowledge Aggregator** as a **materialized VIEW** over existing authoritative sources. No greenfield knowledge engine. No SSOT duplication.

---

## 2. Sources read (graceful if missing)

| Source file | Role |
|-------------|------|
| `tae_intraday_discovery_engine.json` | Intraday patterns + ticker learning |
| `tae_evidence_engine_report.json` | Confirmed evidence items |
| `tae_runtime_learning_memory.json` | Strategy tracking + conflicts |
| `runtime_outputs/tae_intraday_fade_history.csv` | Fade observation metadata |
| `runtime_outputs/tae_intraday_fade_daily_summary.json` | Daily run counts |
| `tae_knowledge_candidates.json` | Knowledge candidates (optional) |
| `tae_discovery_hypothesis_rankings.json` | Discovery hypothesis rankings (optional) |

Missing files are recorded in `sources_loaded: false` — aggregation continues.

---

## 3. Outputs created

| File | Description |
|------|-------------|
| `tae_knowledge_base.json` | Canonical consolidated VIEW |
| `tae_knowledge_base.md` | Full catalog by section |
| `tae_knowledge_summary.md` | Executive summary |

---

## 4. What gets normalized

Each upstream finding → **Knowledge Entry** with:

`id`, `title`, `description`, `source`, `source_file`, `category`, `subject`, `pattern_type`, `first_seen`, `last_seen`, `observations`, `confidence`, `trend`, `status`, `evidence_refs`, `metrics`, `recommendation`, `shadow_only`

### Status rules

| Condition | Status | Confidence |
|-----------|--------|------------|
| Intraday observations < 30 | EXPERIMENTAL | LOW |
| Intraday observations 30–99 | LEARNING | MEDIUM |
| Intraday observations ≥ 100 | CONFIRMED | HIGH |
| Evidence `CONFIRMED` | CONFIRMED | HIGH |
| Evidence `REJECTED` | RETIRED | LOW |
| Learning `sample_insufficient` | EXPERIMENTAL | LOW |
| Knowledge candidates sample ≥ 100 | CONFIRMED | HIGH |

### Trend (1A)

All entries default to **NEW**. Evolution diff deferred to X.KNOWLEDGE-1B.

### Recommendations (SHADOW only)

`CONTINUE_OBSERVATION`, `PRIORITIZE_TRACKING`, `TEST_TRAILING_SHADOW`, `TEST_PARTIAL_SELL_SHADOW`, `INSUFFICIENT_DATA` — never BUY/SELL.

### Dedupe

Key: `(source, subject, pattern_type)` — merges observations, evidence_refs, last_seen.

---

## 5. Tests run

```bash
python3 -m py_compile tae_knowledge_base.py
python3 tae_knowledge_base_test.py
python3 tae_knowledge_base.py
python3 -m py_compile live_bot.py tae_intraday_discovery_engine.py tae_intraday_fade_history.py
```

| Test | Validates |
|------|-----------|
| `test_missing_files_handled_gracefully` | Empty base, no crash |
| `test_intraday_discovery_normalization` | Pattern → entry, LOW/EXPERIMENTAL |
| `test_evidence_normalization` | CONFIRMED → HIGH |
| `test_learning_memory_normalization` | Blocked tracking → INSUFFICIENT_DATA |
| `test_deduplication` | Same key → one entry |
| `test_confidence_scoring_rules` | 10/50/120 observation tiers |
| `test_status_assignment_evidence` | Upstream CONFIRMED passthrough |
| `test_no_buy_sell_recommendations` | BUY/SELL sanitized |
| `test_json_and_markdown_output` | VIEW type + MD sections |

---

## 6. Confirmations

| Check | Status |
|-------|--------|
| SHADOW_ONLY | **YES** |
| PAPER_ONLY | **YES** |
| NO_BROKER | **YES** |
| `live_bot.py` untouched | **YES** |
| Discovery Engine untouched | **YES** |
| Market Data Layer untouched | **YES** |
| Knowledge Base is VIEW not SSOT | **YES** — `view_type: MATERIALIZED_VIEW` |
| Git commit | **NO** |

---

## 7. Knowledge Base = VIEW, not SSOT

- Upstream writers remain authoritative (`evidence_engine`, `intraday_discovery`, `learning_memory`, etc.).
- `tae_knowledge_base.json` is regenerated on each run — safe to delete and rebuild.
- Downstream consumers should treat missing upstream files as source gaps, not knowledge deletion.

---

## 8. Next: X.KNOWLEDGE-1B Confidence Evolution

1. Load previous `tae_knowledge_base.json` and diff entries
2. Compute trend: IMPROVING / STABLE / DECLINING
3. Upgrade/downgrade confidence when observation thresholds crossed
4. Emit `evolution_changelog` in JSON
5. Mark DECLINING when pattern absent from recent source runs

---

*TAE X.KNOWLEDGE-1A — read-only knowledge aggregator implemented.*
