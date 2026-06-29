# TAE Market Psychology & Event Intelligence Blueprint

**Document type:** Architecture blueprint (Phase 1 — design only)  
**Version:** 1.0  
**Date:** 2026-06-29  
**Status:** DRAFT FOR ARCHITECT REVIEW  
**Safety mode:** `ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE`

---

## 1. Executive Summary

TAE has completed its first full historical research cycle: **1,600 jobs**, **1,475 completed backtests**, statistical validation, robust/weak strategy shortlists, and meta-intelligence recommendations. The next capability gap is **contextual market intelligence** — understanding *why* markets move, *how* participants behave around public events, and *which* discovered strategies are resilient or fragile under specific psychological and event regimes.

This blueprint defines **TAE Market Psychology & Event Intelligence (TAE-MPEI)**: a read-only research layer that ingests **public, legally accessible data only**, builds a structured **Historical Event Memory**, detects **market psychology states**, measures **pre-event public positioning**, models **post-event reactions and recovery**, and feeds calibrated insights into **Meta Intelligence** and **Strategy Evolution**.

**Core principles:**

| Principle | Requirement |
|-----------|-------------|
| Legal data only | Public news, filings, calendars, market/options data — no MNPI, no insider channels |
| No look-ahead | All features timestamped ≤ decision time; event surprise computed from published expectations only |
| Research-only | No broker, no execution, no portfolio mutation |
| Evidence-linked | Every inference cites event IDs, data sources, and confidence scores |
| Horizon-aware | Separate 2Y / 5Y / 10Y / 20Y cohorts; no pooling without explicit weighting |

**Expected outcome:** TAE gains the ability to answer questions such as: *"How did DISCOVERY_0027 perform during FOMC surprise hikes vs. relief cuts?"*, *"Is current psychology CAPITULATION or DISTRIBUTION?"*, and *"What is median recovery time after CPI upside surprises in US equities?"*

**Recommendation:** **GO** for phased implementation starting with Event Schema + Memory Scaffold (Phase 2). Rationale in Section 12.

---

## 2. Architecture Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXISTING TAE ARTIFACTS                               │
│  tae_historical_execution.json  │  tae_historical_results_analysis.json     │
│  tae_strategy_discovery.json    │  tae_strategy_simulation.json             │
│  tae_meta_intelligence.json     │  tae_meta_evolution.json                  │
│  tae_daily_intelligence_report.json                                          │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 0: Historical Results Baseline                                       │
│  Strategy performance by market × horizon; robust/weak cohorts; trade stats │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: Event Intelligence                                                  │
│  Public event ingestion │ taxonomy │ surprise │ severity │ asset linkage    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: Historical Event Memory (Event Memory Store)                        │
│  Indexed archive: event → market state before → reactions after → recovery  │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌───────────────────────────────┐   ┌───────────────────────────────────────┐
│  LAYER 3: Psychology State     │   │  LAYER 4: Pre-Event Positioning        │
│  Detector                       │   │  Detector (public signals only)        │
│  PANIC / FOMO / RISK_OFF / …   │   │  IV expansion, volume, rotation, …     │
└───────────────┬───────────────┘   └───────────────────┬───────────────────┘
                │                                       │
                └───────────────────┬───────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 5: Market Reaction Model + Recovery Time Model                         │
│  Multi-horizon return / MAE / MFE / vol / breadth / strategy overlay          │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 6: Strategy Impact Mapper                                              │
│  Maps events + psychology → strategy performance deltas vs. baseline          │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 7: Meta Intelligence (extended)                                        │
│  Event-aware confidence │ regime warnings │ promotion/retirement context       │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 8: Strategy Evolution (extended)                                       │
│  Event-conditioned hypotheses │ feature bias │ discovery seed adjustments    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data flow summary:**

1. **Historical Results** provide strategy baselines and ticker universes per market.
2. **Event Intelligence** normalizes public events into a canonical schema.
3. **Event Memory** stores each event with pre/post market snapshots.
4. **Psychology Detector** classifies rolling market state from observable metrics.
5. **Pre-Event Positioning Detector** flags abnormal public positioning before known calendar events.
6. **Reaction + Recovery Models** quantify asset and strategy behavior across time windows.
7. **Strategy Impact Mapper** joins reaction stats with `tae_historical_execution.json` job metrics.
8. **Meta Intelligence** consumes summaries for confidence adjustment and human-review recommendations.
9. **Strategy Evolution** uses event-conditioned learnings to bias (not auto-modify) discovery seeds.

---

## 3. Components

### 3.1 Event Intelligence

**Purpose:** Ingest, normalize, classify, and score public market events.

**Responsibilities:**
- Parse earnings calendars, macro release schedules, SEC filing timestamps, public news headlines
- Assign event taxonomy category and unique `event_id`
- Compute surprise (actual vs. consensus where publicly published)
- Assign severity (1–5) and affected asset universe
- Emit `tae_event_intelligence.json` registry entries

**Inputs:** Public calendars, news APIs, filing feeds, macro data releases  
**Outputs:** Canonical event records ready for Event Memory indexing  
**Does NOT:** Scrape paywalled leaks, access embargoed data, or infer non-public information

---

### 3.2 Market Psychology Engine

**Purpose:** Classify aggregate market psychology state from observable public market metrics.

**Responsibilities:**
- Compute rolling psychology state (one primary + optional secondary state)
- Attach confidence score and supporting metric bundle
- Detect state transitions and duration
- Flag false-positive risk factors

**Inputs:** Price/volume, volatility, breadth, correlations, optional public sentiment  
**Outputs:** `psychology_state` time series with confidence; `tae_psychology_state.json`  
**Does NOT:** Infer participant intent from private order flow or dark-pool data unavailable publicly

---

### 3.3 Historical Event Memory

**Purpose:** Durable, queryable archive linking events to market snapshots and outcomes.

**Responsibilities:**
- Store event record + pre-event window metrics + post-event reaction windows
- Index by category, severity, market, date, affected tickers/sectors
- Support similarity search ("find past CPI upside surprises in RISK_OFF regime")
- Version events when revisions occur (e.g., data restatements)

**Inputs:** Event Intelligence records, market data snapshots  
**Outputs:** `tae_event_memory.json` (+ optional partitioned store by year)  
**Does NOT:** Mutate historical execution results or rewrite backtest outcomes

---

### 3.4 Pre-Event Positioning Detector

**Purpose:** Detect statistically abnormal **public** positioning patterns before scheduled or emerging public events.

**Responsibilities:**
- Baseline normal pre-event behavior per event type (e.g., 20 prior FOMC meetings)
- Flag deviations: IV expansion, volume surge, sector rotation, spread widening, correlation breaks
- Assign positioning signal strength and legality attestation flag (`PUBLIC_DATA_ONLY`)

**Inputs:** Options IV/volume/OI, equity volume, sector ETFs, credit spreads (public)  
**Outputs:** `pre_event_signals[]` attached to event memory records  
**Does NOT:** Use whisper numbers from non-public channels, insider transaction timing as predictive signal alone, or scraped restricted forums

---

### 3.5 Market Reaction Model

**Purpose:** Quantify asset-level reaction to events across standard time windows.

**Responsibilities:**
- For each `(event, asset)` pair compute multi-horizon metrics (see Section 7)
- Aggregate by event category, severity, surprise direction, psychology state at event time
- Produce distributional stats (median, p25, p75) not just means

**Inputs:** Event Memory, OHLCV, volume, volatility, breadth  
**Outputs:** `reaction_profiles[]` in `tae_event_reaction_stats.json`  
**Does NOT:** Use post-event news narrative to relabel pre-event features (no hindsight labeling)

---

### 3.6 Recovery Time Model

**Purpose:** Measure time and path for markets/strategies to return to pre-event baseline.

**Responsibilities:**
- Define baseline: pre-event N-day mean return / vol / drawdown reference
- Track recovery duration until metric re-enters baseline band (e.g., ±1σ)
- Record partial recovery, failed recovery, and secondary-shock patterns

**Inputs:** Reaction Model outputs, pre-event baseline windows  
**Outputs:** `recovery_time_to_baseline`, `recovery_path_class` (V-shape, U-shape, L-shape, no recovery)  
**Does NOT:** Assume recovery completes without statistical confirmation

---

### 3.7 Strategy Impact Mapper

**Purpose:** Bridge event/reaction intelligence with TAE strategy backtest artifacts.

**Responsibilities:**
- Overlay historical trades from execution jobs onto event windows
- Compute strategy performance during event vs. non-event periods
- Rank strategies by event-regime resilience (robust under PANIC, fragile under FOMO, etc.)
- Feed Meta Intelligence with event-conditioned strategy scores

**Inputs:** `tae_historical_execution.json`, Event Memory, Reaction Model, `tae_strategy_discovery.json`  
**Outputs:** `tae_strategy_event_impact.json`  
**Does NOT:** Auto-promote or auto-retire strategies; recommendation-only

---

## 4. Data Sources

For each source: **Required (R)**, **Optional (O)**, public/legal status, historical availability, frequency, limitations.

### 4.1 Master Data Source Table

| Data Source | Used By | R/O | Public/Legal | History | Frequency | Limitations |
|-------------|---------|-----|--------------|---------|-----------|-------------|
| **OHLCV price/volume** | All layers | R | Public market data | Decades (vendor-dependent) | Daily; intraday where licensed | Survivorship bias; corporate actions require adjustment |
| **Realized volatility** | Psychology, Reaction | R | Derived public | Same as price | Daily/intraday | Window sensitivity; regime-dependent |
| **Implied volatility (options)** | Pre-Event, Psychology | O | Public options chains | ~15–20Y liquid names | Daily; intraday if subscribed | Illiquid strikes; wide spreads on small caps |
| **Options volume / OI** | Pre-Event | O | Public | Moderate | Daily | Not equivalent to institutional intent |
| **VIX / regional vol indices** | Psychology, Reaction | R | Public | ~30Y (VIX from 1990) | Daily | Index-specific; not stock-level |
| **Earnings calendar** | Event Intelligence | R | Public (exchange, EDGAR, vendors) | Full for listed equities | Quarterly + revisions | Date changes; timezone alignment |
| **Fed / macro calendar** | Event Intelligence | R | Public (Fed, BLS, BEA) | Decades | Scheduled releases | Embargo rules — use published timestamp only |
| **CPI / inflation releases** | Event Intelligence | R | Public (BLS) | Decades | Monthly | Revisions; core vs. headline |
| **Jobs / employment (NFP, etc.)** | Event Intelligence | R | Public (BLS) | Decades | Monthly | Large revision history |
| **SEC / company filings (8-K, 10-K, 10-Q)** | Event Intelligence | R | Public EDGAR | Full for US issuers | Event-driven | Parsing complexity; lag vs. "news" |
| **Public news timestamps** | Event Intelligence | O | Public licensed feeds | Vendor-dependent | Real-time / archive | Duplicate stories; sentiment noise |
| **Sector / market breadth** | Psychology, Reaction | R | Derived public | Decades | Daily | Index composition changes |
| **Cross-asset correlations** | Psychology, Pre-Event | R | Derived public | Decades | Daily/rolling | Unstable in crises |
| **Credit spreads (HYG/LQD, CDX if public)** | Pre-Event, Psychology | O | Public ETFs/proxy | ~15–20Y ETF | Daily | Proxy ≠ full CDS market |
| **Public sentiment scores** | Psychology | O | Public (news/social vendors) | ~10–15Y | Daily | Vendor bias; bot noise |
| **FX / rates (DXY, yields)** | Event Intelligence, Reaction | O | Public | Decades | Daily/intraday | Macro linkage complexity |
| **Commodity prices** | Event Intelligence | O | Public | Decades | Daily | Supply shock exogeneity |

### 4.2 Per-Component Data Requirements

| Component | Required Data | Optional Data |
|-----------|---------------|---------------|
| Event Intelligence | Macro calendar, earnings dates, filing timestamps, headline metadata | News sentiment, geopolitical tags |
| Market Psychology Engine | Price, volume, vol, breadth, correlations | Sentiment, credit spreads |
| Historical Event Memory | All Event Intelligence fields + pre/post snapshots | Full intraday tick archive |
| Pre-Event Positioning | Volume, IV, options OI/volume, sector ETFs | Spread proxies, correlation shifts |
| Market Reaction Model | OHLCV, volume, vol, breadth | Intraday bars for 5m/15m windows |
| Recovery Time Model | Daily OHLCV + baseline windows | Intraday for short recovery paths |
| Strategy Impact Mapper | `tae_historical_execution.json` trades/metrics, event windows | Discovery metadata |

### 4.3 Legal & Compliance Guardrails

| Allowed | Prohibited |
|---------|------------|
| Exchange-published prices and volumes | Material non-public information (MNPI) |
| EDGAR filings after public release timestamp | Embargoed economic data before release |
| Licensed public news with attribution | Scraping restricted / ToS-violating sources |
| Consensus estimates from public aggregators | "Whisper numbers" from non-public channels |
| Options chain data from public vendors | Insider trading patterns as standalone alpha signal |
| Government statistical releases post-publish | Private Telegram/Discord leak groups |

Every ingested record MUST carry: `source`, `published_at`, `license_class`, `public_data_attestation: true`.

---

## 5. Event Taxonomy

### 5.1 Category Definitions

Each event record includes core fields:

```
event_id, category, subcategory, title, published_at, scheduled_at,
timezone, severity, surprise_score, surprise_direction,
expected_value, actual_value, unit, consensus_source,
affected_markets[], affected_sectors[], affected_tickers[],
source, source_url, public_data_attestation
```

**Severity scale (1–5):**

| Level | Label | Description |
|-------|-------|-------------|
| 1 | MINOR | Routine; limited market impact expected |
| 2 | LOW | Notable but localized |
| 3 | MODERATE | Sector or single-market impact |
| 4 | HIGH | Broad index impact |
| 5 | EXTREME | Systemic shock (e.g., GFC-style, pandemic declaration) |

**Surprise calculation (when applicable):**

```
surprise_raw = actual_value - expected_value
surprise_pct = surprise_raw / |expected_value|  (if expected ≠ 0)
surprise_direction = SIGN(surprise_raw)  → POSITIVE | NEGATIVE | INLINE (within threshold)
surprise_score = normalized z-score vs. trailing N surprises of same category
```

Threshold for INLINE: `|surprise_pct| < category_inline_threshold` (e.g., CPI: 0.05%, NFP: 20k jobs).

---

### 5.2 Category Reference

| Category | Subcategories | Key Fields | Surprise Fields | Affected Assets |
|----------|---------------|------------|-----------------|-----------------|
| **MACRO** | GDP, PMI, retail sales | actual, expected, period | GDP QoQ, PMI level | Index ETFs, rates, FX |
| **FED** | FOMC rate decision, minutes, speech | decision_bps, statement_tone | vs. Fed funds futures | SPY, TLT, DXY, banks |
| **CPI / inflation** | CPI, core CPI, PCE | mom, yoy | vs. consensus | Rates, growth vs. value |
| **JOBS / employment** | NFP, unemployment, JOLTS | headline, revisions | vs. consensus | Cyclicals, rates |
| **EARNINGS** | EPS, revenue | eps_actual, eps_est | eps_surprise_pct | Single stock, sector |
| **GUIDANCE** | raise, cut, maintain | guidance_range | vs. street | Single stock |
| **GEOPOLITICAL** | conflict, sanctions, election | region, actors | qualitative severity | Commodities, defense, FX |
| **REGULATORY** | FDA, antitrust, SEC action | agency, ruling | binary / severity | Sector, single name |
| **CREDIT / BANKING** | bank failure, downgrade, stress test | institution, magnitude | spread_change | Financials, HY |
| **COMMODITY** | OPEC, inventory, weather | supply_delta | vs. expected | Energy, materials |
| **COMPANY_SPECIFIC** | M&A, CEO change, product | company, action | market reaction proxy | Single ticker |
| **SECTOR_ROTATION** | factor shift, rebalancing | from_sector, to_sector | flow_zscore | Sector ETFs |

---

## 6. Psychology State Taxonomy

### 6.1 State Definitions

Each state snapshot includes: `state`, `confidence` (0–1), `metrics{}`, `since`, `transition_from`, `false_positive_risks[]`.

| State | Observable Signals | Required Metrics | Confidence Drivers | False-Positive Risks |
|-------|-------------------|------------------|--------------------|-----------------------|
| **PANIC** | Sharp selloff, vol spike, correlation→1 | 1d return < -2σ, VIX spike > 30%, breadth collapse | Magnitude + breadth confirmation | Single-name flash crash |
| **CAPITULATION** | High volume down day after extended decline | Volume > 2× avg, RSI < 25, negative breadth extreme | Volume climax + prior drawdown depth | Low-liquidity holiday session |
| **RELIEF_RALLY** | Sharp bounce after known overhang removed | 1d return > +2σ after prior negative event window | Event linkage + vol crush | Short squeeze without fundamentals |
| **FOMO** | Chasing momentum, narrow leadership | New 52w highs surge, low vol grind up, retail flow proxy | Breadth narrowing + momentum stretch | Low-volume drift |
| **GREED** | Extended risk appetite, compressed spreads | VIX < 15, credit spreads tight, euphoria breadth | Duration + low vol persistence | Pre-event calm misread as greed |
| **COMPLACENCY** | Ultra-low vol, tight ranges | Realized vol < historical p10, range contraction | Sustained low vol period | Summer doldrums |
| **DISTRIBUTION** | Flat/up price on declining breadth | Price flat, advance/decline falling, volume up on down days | Wyckoff-style divergence signals | Index rebalancing noise |
| **ACCUMULATION** | Flat/down price on improving internals | Price weak but breadth improving, volume on up days | Duration of divergence | Sector-specific rotation |
| **RISK_OFF** | Flight to quality | Bonds up, equities down, USD up, gold up | Multi-asset confirmation | Intraday whipsaw |
| **RISK_ON** | Cyclicals outperform, credit tightens | High beta outperformance, HYG strength | Cross-asset alignment | One-day squeeze |

**Confidence score formula (conceptual):**

```
confidence = weighted_mean(metric_zscores) × transition_consistency × data_quality_factor
```

Minimum confidence for Meta Intelligence consumption: **0.60**. Below 0.60 → state reported as `UNCERTAIN` with top-2 candidate states.

---

## 7. Historical Reaction Model

### 7.1 Time Windows

For each `(event_id, asset_id)` measure at:

| Window | Offset from Event Timestamp |
|--------|----------------------------|
| T+5m | 5 minutes |
| T+15m | 15 minutes |
| T+1h | 1 hour |
| T+4h | 4 hours |
| T+1d | 1 trading day |
| T+3d | 3 trading days |
| T+1w | 5 trading days |
| T+1m | 21 trading days |

**Event timestamp rules:**
- **Scheduled macro:** Official release `published_at` from source
- **Earnings:** First public release (BMO/AMC convention documented per record)
- **Geopolitical:** First credible public wire timestamp (not retrospective narrative time)
- **Filings:** EDGAR acceptance datetime

Intraday windows (5m–4h) require intraday data license; Phase 4 may start daily-only with intraday deferred.

### 7.2 Metrics per Window

| Metric | Definition |
|--------|------------|
| `return_pct` | `(price_T+n - price_T0) / price_T0 × 100` |
| `max_adverse_excursion` | Worst drawdown from T0 through T+n |
| `max_favorable_excursion` | Best unrealized gain from T0 through T+n |
| `volume_spike` | `volume_T0..n / trailing_20d_avg_volume` |
| `volatility_change` | `realized_vol_post / realized_vol_pre` |
| `breadth_change` | Δ advance/decline ratio vs. pre-event baseline |
| `recovery_time_to_baseline` | Days until return_pct re-enters pre-event ± band |
| `strategy_performance_during_event` | Per-strategy PnL/trade stats from execution overlay |

### 7.3 Aggregation

Store distributions per `(category, severity, surprise_direction, market, psychology_state_at_event)`:

- median, mean, p10, p25, p75, p90 (prefer median for return_pct per X.5 validation)
- sample_count, earliest_event_date, latest_event_date

---

## 8. Pre-Event Positioning

### 8.1 Legal Public Signals Only

| Signal | Detection Method | Lookback Baseline |
|--------|------------------|-------------------|
| Abnormal volume | Z-score vs. 20d same-DOW average | Per ticker / sector ETF |
| IV expansion | IV rank > 80 or ΔIV > 2σ vs. 20d | Per ticker, earnings-grouped |
| Options volume / OI | Call+put volume > 3× avg; OI build | Public options chain |
| Sector rotation | Relative strength shift > 2σ between sector ETFs | 5d vs. 60d |
| Spread widening | HYG-LQD, TED proxy widening > 1.5σ | 20d |
| Correlation shift | Pairwise corr change > 2σ | Rolling 20d vs. 120d |
| Liquidity changes | Amihud illiquidity spike, bid-ask widening (if public) | 20d |

Each signal record:

```
signal_type, detected_at, zscore, baseline_window, public_data_attestation: true,
legal_status: PUBLIC_ONLY, excluded: false
```

### 8.2 Explicit Exclusions

The following MUST NOT be ingested, inferred, or used:

- Private leaks or non-public information
- Embargoed macro data obtained before official release
- Scraping restricted sources (paywall bypass, ToS violations)
- Insider material or MNPI
- Non-attributable "whisper" consensus
- Dark pool prints unavailable via public vendors
- Proprietary bank trader commentary not publicly published

**Audit requirement:** Pre-event module emits `legal_compliance_attestation` block on every run; any source without public timestamp is rejected.

---

## 9. Integration with Existing TAE

### 9.1 Artifact Integration Map

| Existing Artifact | Role in TAE-MPEI | Integration Point |
|-------------------|------------------|-------------------|
| **`tae_historical_execution.json`** | Primary strategy performance ground truth (1,475 completed jobs). Provides per-job metrics, trade counts, tickers, market, horizon. | Strategy Impact Mapper overlays event windows on job periods; compares event vs. non-event trade performance. |
| **`tae_historical_results_analysis.json`** | Robust/weak shortlists, strategy families, statistical appendix. | Seeds which strategies to prioritize for event-regime testing; robust list (e.g., DISCOVERY_0027) becomes first event-overlay cohort. |
| **`tae_strategy_discovery.json`** | 100 discovery strategies with entry/exit/market/holding/risk features. | Strategy Impact Mapper joins feature vectors to event sensitivity; Meta Evolution uses event fragility to bias discovery seeds. |
| **`tae_strategy_simulation.json`** | Simulation queue linking strategies to markets/horizons. | Defines universe of `(strategy, market, horizon)` tuples for event-conditioned re-simulation requests (Phase 8). |
| **`tae_meta_intelligence.json`** | Strategic observations, promotion/retirement candidates, ecosystem confidence. | Extended with `event_context` block: current psychology, upcoming events, strategy event-resilience scores. Adjusts confidence — does NOT auto-promote. |
| **`tae_meta_evolution.json`** | Review-only recommendations (CONTINUE_PAPER, RETIRE, INVESTIGATE). | New recommendation categories: `EVENT_REGIME_CAUTION`, `EVENT_REGIME_FAVORABLE`, `EXPAND_EVENT_DATA`. |
| **`tae_daily_intelligence_report.json`** | Daily governance and ecosystem health. | New section: `market_event_intelligence_summary` — active psychology, calendar next 7d, recent reaction stats. |

### 9.2 New Artifacts (Future Phases)

| Artifact | Phase | Schema Name |
|----------|-------|-------------|
| `tae_event_intelligence.json` | 3 | `tae_event_intelligence` |
| `tae_event_memory.json` | 2–3 | `tae_event_memory` |
| `tae_psychology_state.json` | 5 | `tae_psychology_state` |
| `tae_event_reaction_stats.json` | 4 | `tae_event_reaction_stats` |
| `tae_pre_event_positioning.json` | 6 | `tae_pre_event_positioning` |
| `tae_strategy_event_impact.json` | 8 | `tae_strategy_event_impact` |

### 9.3 Module Placement (Future — Not Built in Phase 1)

```
research_core/market_intelligence/
  event_schema.py              # Phase 2
  event_memory_store.py        # Phase 2
  event_ingestion/             # Phase 3
  reaction_model.py            # Phase 4
  recovery_model.py            # Phase 4
  psychology_engine.py         # Phase 5
  pre_event_positioning.py     # Phase 6
  strategy_event_mapper.py     # Phase 8
  reports/                     # JSON/TXT emitters per phase
```

Meta Intelligence extension (Phase 7): read-only consumer in `research_core/meta_intelligence/` — new observation builder, no changes to execution path.

---

## 10. Implementation Phases

### Phase 1: Blueprint Only ← **CURRENT**

| Item | Detail |
|------|--------|
| **Objective** | Define architecture, taxonomies, data contracts, integration map, safeguards |
| **Inputs** | Existing TAE artifacts, historical execution results, statistical validation findings |
| **Outputs** | `TAE_MARKET_INTELLIGENCE_BLUEPRINT.md` |
| **Stop condition** | Architect review PASS |
| **Do NOT build** | Any Python modules, data ingestion, runtime wiring, broker connection |

---

### Phase 2: Event Schema + Memory Scaffold

| Item | Detail |
|------|--------|
| **Objective** | Canonical event schema, memory store interface, empty registry with validation |
| **Inputs** | Blueprint taxonomies (Sections 5–6, 13) |
| **Outputs** | `tae_event_memory.json` (schema v1, 0 events), schema constants, demo script |
| **Stop condition** | Schema validates; empty store round-trips; demo PASS |
| **Do NOT build** | Live ingestion, psychology detector, meta integration, prediction models, strategy modification |

#### X.6A Schema Metadata Requirements (Mandatory)

Every schema object created in X.6A MUST include these fields at the object level (registry root and every storable record type):

| Field | Type | Rule |
|-------|------|------|
| `created_at` | ISO-8601 UTC | Set once at creation; never modified |
| `updated_at` | ISO-8601 UTC | Set at creation; updated on every persisted mutation |
| `schema_version` | integer | Current version of this record shape; see forward-compatibility rules below |
| `source_module` | string | Originating module path (e.g. `research_core/market_intelligence/event_memory_store`) |
| `tae_version` | string | TAE release/build identifier at write time |

**Immutable event IDs:**

- Every event MUST receive a permanent `event_id` at creation time.
- `event_id` MUST NOT change across updates, re-ingestion, or context enrichment.
- Revisions or corrections create a new record with a new `event_id` and an optional `supersedes_event_id` pointer — never overwrite the original ID.
- ID format (blueprint default): `EVT_{category}_{YYYYMMDD}_{sequence}` (e.g. `EVT_CPI_20240312_0001`).

**Forward compatibility:**

- All schemas MUST be forward-compatible: new fields may be added; existing fields MUST NOT be removed or renamed in-place.
- Unknown fields on read MUST be preserved (pass-through) and MUST NOT cause validation failure.
- Required-field sets are defined per `schema_version`; readers MUST support all versions ≤ current.

**Deprecation policy:**

- Deprecation is handled exclusively by incrementing `schema_version` and documenting field status in a version manifest — **never by breaking or mutating old records**.
- Deprecated fields remain readable indefinitely; writers for new records omit deprecated fields unless back-filling legacy exports.
- A `schema_version_manifest` (embedded or sibling constant) maps each version to: added fields, deprecated fields (read-only), required fields.

**X.6A scope boundary:**

- Implementation in X.6A is **schema support only**: types, validation, empty store, metadata fields, ID assignment rules, version manifest.
- No ingestion, no live data population, no reaction/psychology/positioning logic beyond field definitions.

---

### Phase 3: Historical Event Ingestion

| Item | Detail |
|------|--------|
| **Objective** | Backfill public events (macro, earnings, major geopolitical) 2Y–20Y where data exists |
| **Inputs** | Public calendars, EDGAR, licensed news archives |
| **Outputs** | `tae_event_intelligence.json`, populated `tae_event_memory.json` |
| **Stop condition** | ≥500 events indexed; 100% carry `public_data_attestation`; timestamp audit PASS |
| **Do NOT build** | Reaction stats, strategy overlay, real-time feeds |

---

### Phase 4: Reaction Statistics

| Item | Detail |
|------|--------|
| **Objective** | Compute multi-window reaction profiles and recovery times per event category |
| **Inputs** | Event Memory, OHLCV (daily minimum; intraday if available) |
| **Outputs** | `tae_event_reaction_stats.json` |
| **Stop condition** | All 12 categories have ≥10 events with T+1d stats; walk-forward validation PASS |
| **Do NOT build** | Psychology detector, pre-event positioning, meta integration |

---

### Phase 5: Psychology Detector

| Item | Detail |
|------|--------|
| **Objective** | Classify rolling psychology states with confidence scores |
| **Inputs** | Price, vol, breadth, correlations |
| **Outputs** | `tae_psychology_state.json`, historical state timeline |
| **Stop condition** | 10 states defined; backtested transition accuracy report; false-positive audit |
| **Do NOT build** | Pre-event positioning, strategy impact, execution logic |

---

### Phase 6: Pre-Event Positioning Detector

| Item | Detail |
|------|--------|
| **Objective** | Detect abnormal public positioning before scheduled events |
| **Inputs** | Volume, IV, options OI, sector ETFs |
| **Outputs** | `tae_pre_event_positioning.json` |
| **Stop condition** | Legal attestation on 100% signals; baseline comparison for FOMC + earnings |
| **Do NOT build** | Non-public data connectors, real-time trading triggers |

---

### Phase 7: Integration into Meta Intelligence

| Item | Detail |
|------|--------|
| **Objective** | Extend Meta Intelligence observations with event/psychology context |
| **Inputs** | All TAE-MPEI artifacts + existing meta inputs |
| **Outputs** | Extended `tae_meta_intelligence.json`, `tae_daily_intelligence_report.json` sections |
| **Stop condition** | Meta demo PASS; confidence adjustments documented; still REVIEW_ONLY |
| **Do NOT build** | Auto-promotion, broker execution, portfolio changes |

---

### Phase 8: Strategy Impact Learning

| Item | Detail |
|------|--------|
| **Objective** | Map event regimes to strategy performance; feed Meta Evolution |
| **Inputs** | `tae_historical_execution.json`, Event Memory, Reaction stats, Discovery registry |
| **Outputs** | `tae_strategy_event_impact.json`; extended `tae_meta_evolution.json` recommendations |
| **Stop condition** | Robust shortlist event-resilience scored; 2Y/5Y/10Y/20Y cohorts reported separately |
| **Do NOT build** | Automatic strategy rule mutation, discovery engine auto-rewrite |

---

## 11. Anti-Overfitting Safeguards

| Safeguard | Implementation |
|-----------|----------------|
| **No look-ahead bias** | All features use data with `timestamp ≤ decision_time`; strict event-time alignment |
| **Timestamp integrity** | Every record: `source`, `published_at`, `ingested_at`; reject future-dated fields |
| **Event-time alignment** | Reaction windows anchored to official `published_at`; no retroactive relabeling |
| **Out-of-sample validation** | Train reaction baselines on pre-2015; validate 2015–2020; holdout 2020+ |
| **Walk-forward event validation** | Rolling 5Y train → 1Y test for surprise→return relationships |
| **Horizon cohort separation** | Report 2Y / 5Y / 10Y / 20Y separately; no pooled "global average return" without median |
| **Avoid future news context** | NLP features only from headlines published ≤ T0; no summary articles written days later |
| **Survivorship awareness** | Document index constituent changes; prefer index-level analysis for long horizons |
| **Multiple-testing control** | Bonferroni or FDR when scanning many event×strategy pairs |
| **Confidence floors** | Psychology and positioning signals below 0.60 confidence excluded from Meta decisions |
| **Human review gate** | All Meta Evolution event recommendations require `required_human_review: true` |

---

## 12. Final Decision

### GO / NO-GO: **GO**

**Rationale:**

1. **Foundation ready:** 1,475 completed historical jobs provide strategy baselines for event overlay (Phase 8).
2. **Clear gap:** TAE ranks strategies by aggregate metrics but lacks regime/event context — explicitly requested next phase.
3. **Legal feasibility:** All proposed data sources are publicly available; MNPI exclusions are enforceable by schema design.
4. **Incremental risk:** Phased delivery allows stopping after any phase with usable artifacts; no broker or portfolio exposure.
5. **Statistical lesson applied:** X.5 validation showed mean metrics are outlier-driven — reaction model will use medians by default.

**Conditions for GO:**

- Maintain `RESEARCH_ONLY | NO_BROKER | NO_EXECUTION` through Phase 7
- Phase 3 ingestion must pass legal attestation audit before Phase 4
- Intraday windows deferred until daily pipeline validated

### First Implementation Task (Phase 2 only)

**Task:** `X.6A — Event Schema + Memory Scaffold`

1. Create `research_core/market_intelligence/event_schema.py` with canonical event + psychology + reaction + `pre_event_context` field definitions from this blueprint
2. Create `research_core/market_intelligence/event_memory_store.py` with empty registry, JSON persistence, schema validation
3. Create `tae_phase11_event_memory_demo.py` emitting empty `tae_event_memory.json` with `verdict: EVENT_MEMORY_SCAFFOLD_READY`
4. Do NOT ingest live data, do NOT modify existing modules, do NOT connect broker

**Mandatory metadata on every schema object:** `created_at`, `updated_at`, `schema_version`, `source_module`, `tae_version`

**Mandatory event rules:** immutable `event_id`; forward-compatible schemas; deprecation via `schema_version` only — never break old records

**Scope limit:** schema support only — no implementation beyond validation, empty store, and demo emit

**Stop before commit.** Architect review required.

---

## 13. Market Context Layer

### 13.1 Purpose

Every historical event stored in Event Memory MUST include a **pre-event market context snapshot** captured immediately before the event timestamp. Event reactions are not determined by the headline alone — they are determined by the **interaction between the event and the prevailing market environment**.

The Market Context Layer is a mandatory enrichment pass applied at event ingestion time (Phase 3) and persisted alongside each event record in `tae_event_memory.json`. It does not alter the architecture map in Section 2; it defines **additional required fields** on every event memory entry.

### 13.2 Pre-Event Context Window

| Parameter | Value |
|-----------|-------|
| Snapshot anchor | Last available market close **before** `event.published_at` (or last intraday bar before release for scheduled macro) |
| Lookback for rolling metrics | 20 trading days unless noted |
| Context block label | `pre_event_context` |
| Immutability | Frozen at ingestion; revisions create new context version, never overwrite |

For scheduled releases (FOMC, CPI, NFP, earnings AMC/BMO), the context snapshot uses the **last completed session prior to release**. For unscheduled events (geopolitical, regulatory), the snapshot uses the last bar before the first public wire timestamp.

### 13.3 Required Context Fields

Each event record MUST include the following under `pre_event_context`:

| Field | Description | Primary Source | Required |
|-------|-------------|----------------|----------|
| `market_regime` | Classified regime: BULL / BEAR / SIDEWAYS / TRANSITION (see 13.4) | Price trend + breadth | **Yes** |
| `psychology_state` | Primary psychology state at snapshot (Section 6) | Psychology Engine | **Yes** |
| `vix` | CBOE VIX level at snapshot | Public index | **Yes** |
| `realized_volatility` | 20d annualized realized vol (SPY or regional index) | Derived public | **Yes** |
| `implied_volatility` | ATM 30d IV for index or event ticker (or VIX as proxy) | Public options / index | **Yes** |
| `breadth` | Advance/decline ratio or % stocks above 50d MA | Derived public | **Yes** |
| `sector_leadership` | Top 1–3 sectors by 20d relative strength | Sector ETFs | **Yes** |
| `sector_weakness` | Bottom 1–3 sectors by 20d relative strength | Sector ETFs | **Yes** |
| `treasury_yields` | 2Y, 10Y, and 2s10s spread | Public rates | **Yes** |
| `usd_index` | DXY or trade-weighted USD proxy | Public FX index | **Yes** |
| `oil` | WTI or Brent front-month proxy (USO/CL) | Public commodity | **Yes** |
| `gold` | GLD or spot gold proxy | Public commodity | **Yes** |
| `credit_spreads` | HY OAS proxy (HYG-LQD spread or index) | Public ETF proxy | Optional* |
| `correlation_regime` | LOW / NORMAL / HIGH / CRISIS (see 13.5) | Rolling cross-asset corr | **Yes** |
| `liquidity_regime` | NORMAL / STRESSED / IMPAIRED (see 13.6) | Volume, spreads, Amihud | **Yes** |
| `context_captured_at` | ISO timestamp of snapshot bar | System | **Yes** |
| `context_data_quality` | COMPLETE / PARTIAL / DEGRADED | Validation | **Yes** |

\*Credit spreads marked optional when public proxy unavailable for date/market; `context_data_quality` MUST reflect PARTIAL if omitted.

### 13.4 Market Regime Classification

`market_regime` is derived from public metrics only, using rules aligned with Section 6 psychology states but at a coarser grain:

| Regime | Observable Criteria |
|--------|---------------------|
| **BULL** | Index above 200d MA; 50d return > 0; breadth > median 1Y |
| **BEAR** | Index below 200d MA; 50d return < 0; breadth < median 1Y |
| **SIDEWAYS** | Index within ±3% of 200d MA for ≥ 20d; low realized vol |
| **TRANSITION** | Regime change in prior 10d or conflicting signals across indices |

Regime is stored as a label plus supporting metrics (`regime_confidence`, `regime_since_days`).

### 13.5 Correlation Regime

| Label | Definition |
|-------|------------|
| **LOW** | Average pairwise equity correlation < 20d p25 (1Y history) |
| **NORMAL** | Between p25 and p75 |
| **HIGH** | Above p75; equity correlation elevated |
| **CRISIS** | Correlation > p95 AND VIX > 30 (or regional equivalent) |

Computed from public index/sector ETF return correlations over 20d rolling window.

### 13.6 Liquidity Regime

| Label | Definition |
|-------|------------|
| **NORMAL** | Volume within ±1σ of 60d avg; no spread widening |
| **STRESSED** | Volume > 1.5σ OR spread proxy > 1.5σ |
| **IMPAIRED** | Volume > 2σ AND spread proxy > 2σ OR market halt conditions |

Uses public volume and ETF bid-ask proxies where available; degraded flag if only volume available.

### 13.7 Why Context Matters — Non-Identical Training Samples

**Core rule:** Two events with the same category, severity, and surprise score MUST NOT be treated as identical training samples if their pre-event market contexts differ materially.

**Example:**

| Event | Context A | Context B |
|-------|-----------|-----------|
| CPI +0.3% surprise | VIX 12, RISK_ON, LOW correlation, BULL regime | VIX 28, RISK_OFF, CRISIS correlation, BEAR regime |
| Expected reaction | Mild rates repricing; equities digest | Volatility expansion; risk assets sell further |
| TAE treatment | Separate cohort in reaction stats | Separate cohort in reaction stats |

**Implications for TAE modules:**

| Module | Context Usage |
|--------|---------------|
| Historical Event Memory | Stores `pre_event_context` as immutable sibling to event fields |
| Market Reaction Model | Aggregates reactions by `(category, surprise_direction, market_regime, correlation_regime)` — not category alone |
| Recovery Time Model | Baseline and recovery path conditioned on liquidity regime |
| Pre-Event Positioning | Signals interpreted relative to context (IV expansion in COMPLACENCY ≠ same in PANIC) |
| Strategy Impact Mapper | Strategy fragility scored per context cluster, not global event type |
| Meta Intelligence | Flags when current context has no close historical analogue (low similarity) |

**Anti-pattern (prohibited):** Pooling all CPI upside surprises into one distribution regardless of VIX, regime, or breadth — this inflates false confidence and violates walk-forward validity.

### 13.8 Context Similarity Score

When TAE searches Historical Event Memory for **analogue events** (similar past situations to inform reaction expectations, strategy impact, or Meta Intelligence warnings), it MUST rank candidates by a **Context Similarity Score** in addition to event-type match.

#### 13.8.1 Definition

```
Context Similarity Score (CSS) ∈ [0.0, 1.0]

CSS = weighted_mean(similarity_i) × data_quality_factor × recency_decay(optional)

where similarity_i = 1 - min(|z_current_i - z_candidate_i| / z_scale, 1.0)
```

Each dimension `i` is converted to a z-score vs. trailing 5Y history for that market before comparison. Categorical fields use exact-match or adjacent-match rules (see 13.8.3).

#### 13.8.2 Dimension Weights (default)

| Dimension | Weight | Rationale |
|-----------|--------|-----------|
| `market_regime` | 0.15 | Structural backdrop |
| `psychology_state` | 0.12 | Participant behavior |
| `vix` | 0.10 | Fear gauge |
| `realized_volatility` | 0.08 | Realized stress |
| `implied_volatility` | 0.08 | Forward-looking stress |
| `breadth` | 0.08 | Internal health |
| `sector_leadership` / `sector_weakness` | 0.07 | Rotation pattern (Jaccard overlap on top-3) |
| `treasury_yields` (2s10s spread) | 0.08 | Rate environment |
| `usd_index` | 0.05 | Dollar pressure |
| `oil` | 0.04 | Inflation/growth signal |
| `gold` | 0.04 | Safe-haven demand |
| `credit_spreads` | 0.05 | Credit stress (0 if unavailable; weight redistributed) |
| `correlation_regime` | 0.08 | Contagion risk |
| `liquidity_regime` | 0.08 | Execution environment |

Weights sum to 1.0. Weights are blueprint defaults; Phase 4 may calibrate on out-of-sample data only.

#### 13.8.3 Categorical Match Rules

| Field | Match Score |
|-------|-------------|
| Exact regime/state match | 1.0 |
| Adjacent regime (e.g., BULL ↔ TRANSITION) | 0.5 |
| Opposite regime (e.g., BULL ↔ BEAR) | 0.0 |
| Sector leadership Jaccard (top-3 sets) | \|A ∩ B\| / \|A ∪ B\| |

#### 13.8.4 Analogue Search Procedure

1. Filter Event Memory by: same `category` (or parent category), same `affected_market`, comparable `severity` (±1 level)
2. Require `surprise_direction` match (POSITIVE / NEGATIVE / INLINE) when surprise is defined
3. Compute CSS for all remaining candidates against **current** or **query** context snapshot
4. Return top-K analogues where `CSS ≥ 0.65` (minimum analogue threshold)
5. If no candidate meets threshold → emit `INSUFFICIENT_ANALOGUE` warning to Meta Intelligence; do NOT extrapolate from weak matches

#### 13.8.5 Output Fields for Analogue Results

```
analogue_event_id, context_similarity_score, event_similarity_score,
combined_match_score, reaction_summary_ref, sample_count_warning
```

```
combined_match_score = 0.4 × event_match + 0.6 × CSS
```

Event match covers category, severity, surprise direction. **Context is weighted higher (60%)** because reaction outcomes are context-dependent.

#### 13.8.6 Reporting Requirements

- Reaction statistics MUST report `median_css_of_cohort` when aggregating analogue-based expectations
- Meta Intelligence MUST surface when current context is novel (`max_CSS < 0.65`)
- Daily Intelligence Report includes `context_regime_summary` block referencing current snapshot vs. nearest historical analogue

### 13.9 Phase Integration (Addendum Only — No Architecture Change)

| Phase | Market Context Layer Addition |
|-------|-------------------------------|
| Phase 2 (Schema) | Add `pre_event_context` object to event schema; add CSS field definitions |
| Phase 3 (Ingestion) | Compute and freeze context snapshot for every ingested event |
| Phase 4 (Reaction) | Stratify reaction stats by context clusters; CSS-weighted analogue queries |
| Phase 5 (Psychology) | Psychology state feeds `pre_event_context.psychology_state` |
| Phase 7 (Meta) | Novel-context warnings; analogue confidence in recommendations |
| Phase 8 (Strategy Impact) | Event-regime fragility uses CSS-matched cohorts only |

### 13.10 Safeguards (Context-Specific)

| Rule | Requirement |
|------|-------------|
| No look-ahead | Context snapshot strictly before `published_at`; no post-event vol/breadth |
| No context relabeling | Post-event regime changes do NOT retroactively alter `pre_event_context` |
| Missing data | PARTIAL context allowed; CSS excludes missing dimensions with weight redistribution |
| Overfitting | CSS weights calibrated walk-forward only; holdout 2020+ for validation |
| Transparency | Every analogue query logs dimension-level similarity breakdown |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| MNPI | Material Non-Public Information |
| Event Memory | Indexed store of public events with pre/post market context |
| Psychology State | Classified aggregate market behavior regime |
| Surprise Score | Normalized actual vs. publicly expected value |
| Recovery Time | Duration until metric returns to pre-event baseline band |
| Strategy Impact | Delta in strategy performance during event windows vs. baseline |
| Market Context Layer | Mandatory pre-event snapshot of regime, vol, breadth, cross-asset, and liquidity state |
| Context Similarity Score (CSS) | 0–1 score comparing pre-event context dimensions for historical analogue search |
| Pre-Event Context | Immutable `pre_event_context` block frozen at last bar before event timestamp |
| Schema Metadata | Required fields on every object: `created_at`, `updated_at`, `schema_version`, `source_module`, `tae_version` |
| Forward Compatibility | New fields additive only; unknown fields preserved on read; version manifest tracks deprecations |

## Appendix B: Related TAE Documents

| Document | Status |
|----------|--------|
| Historical execution results (X.4) | Complete — 1475/1600 |
| Historical results analysis (X.5) | Complete |
| Statistical validation appendix | Complete |
| Performance audit (X.4) | Complete |
| This blueprint (X.6 Phase 1) | Current |

---

*End of blueprint. No code. No runtime. No broker. No portfolio changes.*
