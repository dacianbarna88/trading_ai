"""
Event schema — Phase X Sprint X.6A

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Schema definitions only. No ingestion, models, or runtime wiring.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from typing import Any

SCHEMA_NAME = "tae_event_memory"
CURRENT_SCHEMA_VERSION = 1
TAE_VERSION = "X.6A"
SOURCE_MODULE_SCHEMA = "research_core/market_intelligence/event_schema.py"
SOURCE_MODULE_STORE = "research_core/market_intelligence/event_memory_store.py"

METADATA_FIELDS: tuple[str, ...] = (
    "created_at",
    "updated_at",
    "schema_version",
    "source_module",
    "tae_version",
)

EVENT_ID_PATTERN = re.compile(
    r"^EVT_[A-Z0-9_]+_\d{8}_\d{4,}$"
)

REACTION_WINDOWS: tuple[str, ...] = (
    "T+5m",
    "T+15m",
    "T+1h",
    "T+4h",
    "T+1d",
    "T+3d",
    "T+1w",
    "T+1m",
)

REACTION_METRICS: tuple[str, ...] = (
    "return_pct",
    "max_adverse_excursion",
    "max_favorable_excursion",
    "volume_spike",
    "volatility_change",
    "breadth_change",
    "recovery_time_to_baseline",
    "strategy_performance_during_event",
)

PRE_EVENT_CONTEXT_FIELDS: tuple[str, ...] = (
    "market_regime",
    "psychology_state",
    "vix",
    "realized_volatility",
    "implied_volatility",
    "breadth",
    "sector_leadership",
    "sector_weakness",
    "treasury_yields",
    "usd_index",
    "oil",
    "gold",
    "credit_spreads",
    "correlation_regime",
    "liquidity_regime",
    "context_captured_at",
    "context_data_quality",
)

CONTEXT_SIMILARITY_FIELDS: tuple[str, ...] = (
    "context_similarity_score",
    "event_similarity_score",
    "combined_match_score",
    "analogue_event_id",
    "reaction_summary_ref",
    "sample_count_warning",
)


class EventCategory(str, Enum):
    MACRO = "MACRO"
    FED = "FED"
    CPI_INFLATION = "CPI_INFLATION"
    JOBS_EMPLOYMENT = "JOBS_EMPLOYMENT"
    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    GEOPOLITICAL = "GEOPOLITICAL"
    REGULATORY = "REGULATORY"
    CREDIT_BANKING = "CREDIT_BANKING"
    COMMODITY = "COMMODITY"
    COMPANY_SPECIFIC = "COMPANY_SPECIFIC"
    SECTOR_ROTATION = "SECTOR_ROTATION"


class PsychologyState(str, Enum):
    PANIC = "PANIC"
    CAPITULATION = "CAPITULATION"
    RELIEF_RALLY = "RELIEF_RALLY"
    FOMO = "FOMO"
    GREED = "GREED"
    COMPLACENCY = "COMPLACENCY"
    DISTRIBUTION = "DISTRIBUTION"
    ACCUMULATION = "ACCUMULATION"
    RISK_OFF = "RISK_OFF"
    RISK_ON = "RISK_ON"
    UNCERTAIN = "UNCERTAIN"


class SurpriseDirection(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    INLINE = "INLINE"


class MarketRegime(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    TRANSITION = "TRANSITION"


class CorrelationRegime(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRISIS = "CRISIS"


class LiquidityRegime(str, Enum):
    NORMAL = "NORMAL"
    STRESSED = "STRESSED"
    IMPAIRED = "IMPAIRED"


class ContextDataQuality(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    DEGRADED = "DEGRADED"


# Forward-compatible version manifest. Deprecation is additive — old records remain valid.
SCHEMA_VERSION_MANIFEST: dict[int, dict[str, Any]] = {
    1: {
        "description": "Initial event memory scaffold",
        "required_registry_fields": (
            "schema",
            "schema_version",
            "created_at",
            "updated_at",
            "source_module",
            "tae_version",
            "events",
            "event_count",
            "schema_version_manifest",
            "public_data_attestation",
        ),
        "required_event_fields": (
            "event_id",
            "category",
            "title",
            "published_at",
            "severity",
            "public_data_attestation",
            "created_at",
            "updated_at",
            "schema_version",
            "source_module",
            "tae_version",
        ),
        "optional_event_fields": (
            "subcategory",
            "scheduled_at",
            "timezone",
            "surprise_score",
            "surprise_direction",
            "expected_value",
            "actual_value",
            "unit",
            "consensus_source",
            "affected_markets",
            "affected_sectors",
            "affected_tickers",
            "source",
            "source_url",
            "supersedes_event_id",
            "pre_event_context",
            "reaction_windows",
            "context_similarity",
        ),
        "deprecated_fields": (),
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_metadata(*, source_module: str, schema_version: int | None = None) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "created_at": now,
        "updated_at": now,
        "schema_version": schema_version if schema_version is not None else CURRENT_SCHEMA_VERSION,
        "source_module": source_module,
        "tae_version": TAE_VERSION,
    }


def make_event_id(category: str | EventCategory, published_at: datetime | str, sequence: int) -> str:
    category_value = category.value if isinstance(category, EventCategory) else str(category)
    category_token = re.sub(r"[^A-Z0-9]", "_", category_value.upper())
    if isinstance(published_at, str):
        date_token = published_at[:10].replace("-", "")
    else:
        date_token = published_at.strftime("%Y%m%d")
    return f"EVT_{category_token}_{date_token}_{sequence:04d}"


def validate_event_id(event_id: str) -> bool:
    return bool(EVENT_ID_PATTERN.match(event_id))


def _missing_fields(record: dict[str, Any], required: tuple[str, ...]) -> list[str]:
    return [field for field in required if field not in record]


def validate_metadata(record: dict[str, Any], *, context: str) -> list[str]:
    errors: list[str] = []
    missing = _missing_fields(record, METADATA_FIELDS)
    if missing:
        errors.append(f"{context}: missing metadata fields: {', '.join(missing)}")
    version = record.get("schema_version")
    if version is not None and int(version) not in SCHEMA_VERSION_MANIFEST:
        errors.append(f"{context}: unsupported schema_version {version}")
    return errors


def validate_event_record(record: dict[str, Any]) -> list[str]:
    errors = validate_metadata(record, context=f"event[{record.get('event_id', 'UNKNOWN')}]")
    version = int(record.get("schema_version", CURRENT_SCHEMA_VERSION))
    manifest = SCHEMA_VERSION_MANIFEST.get(version)
    if manifest is None:
        return errors

    missing = _missing_fields(record, manifest["required_event_fields"])
    if missing:
        errors.append(
            f"event[{record.get('event_id', 'UNKNOWN')}]: missing required fields: {', '.join(missing)}"
        )

    event_id = record.get("event_id")
    if event_id is not None and not validate_event_id(str(event_id)):
        errors.append(f"event[{event_id}]: invalid immutable event_id format")

    if record.get("public_data_attestation") is not True:
        errors.append(f"event[{record.get('event_id', 'UNKNOWN')}]: public_data_attestation must be true")

    return errors


def validate_registry(registry: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    errors.extend(validate_metadata(registry, context="registry"))

    version = int(registry.get("schema_version", CURRENT_SCHEMA_VERSION))
    manifest = SCHEMA_VERSION_MANIFEST.get(version)
    if manifest is None:
        errors.append(f"registry: unsupported schema_version {version}")
        return False, errors

    missing = _missing_fields(registry, manifest["required_registry_fields"])
    if missing:
        errors.append(f"registry: missing required fields: {', '.join(missing)}")

    if registry.get("schema") != SCHEMA_NAME:
        errors.append(f"registry: schema must be {SCHEMA_NAME}")

    if registry.get("public_data_attestation") is not True:
        errors.append("registry: public_data_attestation must be true")

    events = registry.get("events")
    if not isinstance(events, list):
        errors.append("registry: events must be a list")
    else:
        if registry.get("event_count") != len(events):
            errors.append("registry: event_count must match len(events)")
        seen_ids: set[str] = set()
        for event in events:
            if not isinstance(event, dict):
                errors.append("registry: each event must be an object")
                continue
            event_errors = validate_event_record(event)
            errors.extend(event_errors)
            event_id = event.get("event_id")
            if isinstance(event_id, str):
                if event_id in seen_ids:
                    errors.append(f"registry: duplicate immutable event_id {event_id}")
                seen_ids.add(event_id)

    return len(errors) == 0, errors


def merge_preserve_unknown(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Forward-compatible merge: unknown keys from base are preserved."""
    merged = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_preserve_unknown(merged[key], value)
        else:
            merged[key] = value
    return merged


def empty_pre_event_context_template() -> dict[str, Any]:
    return {field: None for field in PRE_EVENT_CONTEXT_FIELDS}


def empty_reaction_windows_template() -> dict[str, dict[str, Any]]:
    return {window: {metric: None for metric in REACTION_METRICS} for window in REACTION_WINDOWS}
