"""
TAE Advisory Index — Phase X Sprint X.7B

READ_ONLY | REPORT_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Aggregates read-only state of canonical tae_*.json reports for dashboard visibility.
Does not connect to live trading, scoring, risk, sizing, or BUY/SELL.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ADVISORY_INDEX_SAFETY_BANNER = (
    "READ_ONLY | REPORT_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE"
)

TIMESTAMP_KEYS = (
    "generated_at",
    "created_at",
    "report_date",
    "updated_at",
    "last_checkpoint_saved_at",
)

VERDICT_KEYS = (
    "verdict",
    "status",
    "overall_status",
    "health_status",
)

ADVISORY_CATEGORIES = (
    "historical_execution",
    "historical_analysis",
    "strategy_discovery",
    "strategy_ranking",
    "candidate_registry",
    "meta_intelligence",
    "meta_evolution",
    "evidence_engine",
    "event_memory",
    "adapters",
    "health",
    "unknown",
)

# Ordered rules: first match wins. Patterns match report stem (without tae_ / .json).
_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("historical_execution", ("historical_execution",)),
    ("historical_analysis", ("historical_results_analysis", "historical_research")),
    (
        "strategy_discovery",
        (
            "strategy_discovery",
            "discoveries",
            "knowledge_candidates",
            "hypothesis_registry",
            "experiment_results",
            "cross_validation_report",
            "learning_report",
            "research_priorities",
            "patch_review",
            "implementation_patch",
            "strategy_recommendations",
            "strategy_evolution_plan",
        ),
    ),
    (
        "strategy_ranking",
        (
            "continuous_strategy_ranking",
            "hypothesis_rankings",
            "discovery_hypothesis_rankings",
        ),
    ),
    ("candidate_registry", ("candidate_strategy_registry",)),
    (
        "meta_intelligence",
        ("meta_intelligence", "recommendation_outcome", "recommendation_outcome_registry"),
    ),
    ("meta_evolution", ("meta_evolution",)),
    ("event_memory", ("event_memory",)),
    (
        "evidence_engine",
        (
            "evidence_engine_report",
            "evidence_gap_registration",
            "evidence_gap_report",
            "evidence_history",
            "evidence_integration_gate",
            "evidence_integration_report",
            "evidence_dependency_map",
        ),
    ),
    (
        "adapters",
        (
            "adapter_registry",
            "adapter_report",
            "adapter_dependency_map",
            "accounting_adapter_migration",
            "accounting_integration_report",
            "accounting_dependency_map",
            "orchestrator_strategy_adapter_migration",
            "strategy_integration_report",
            "contract_registry",
            "contract_report",
            "contract_dependency_map",
            "performance_pipeline_report",
            "performance_dependency_map",
            "regional_validation_integration",
            "governance_daily_intelligence_migration",
            "strategy_dependency_map",
        ),
    ),
    (
        "health",
        (
            "quick_health_check",
            "full_ecosystem_run",
            "runtime_foundation",
            "ecosystem_inventory",
            "ecosystem_inventory_audit",
            "ecosystem_orchestrator",
            "integration_gap_report",
            "integration_gate_chain",
            "daily_intelligence_report",
            "strategic_performance_audit",
            "v9_6_stable_release",
            "dependency_graph",
            "systemic_interconnection_map",
            "phase_v_legacy_retirement",
            "confidence_registration",
            "confidence_recalibration",
        ),
    ),
)


def _report_stem(filename: str) -> str:
    name = filename
    if name.startswith("tae_"):
        name = name[4:]
    if name.endswith(".json"):
        name = name[:-5]
    return name


def categorize_report(filename: str) -> str:
    stem = _report_stem(filename)
    for category, patterns in _CATEGORY_RULES:
        for pattern in patterns:
            if pattern.endswith("_"):
                if stem.startswith(pattern):
                    return category
            elif stem == pattern or stem.startswith(f"{pattern}_"):
                return category
    return "unknown"


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_timestamp(payload: dict[str, Any]) -> str | None:
    for key in TIMESTAMP_KEYS:
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _extract_verdict(payload: dict[str, Any]) -> str | None:
    for key in VERDICT_KEYS:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    ecosystem = payload.get("ecosystem_health")
    if isinstance(ecosystem, dict):
        value = ecosystem.get("overall_status")
        if value is not None and str(value).strip():
            return str(value)
    return None


def _extract_warnings(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("warnings")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


@dataclass
class ReportIndexEntry:
    filename: str
    category: str
    state: str
    timestamp: str | None = None
    verdict: str | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class AdvisoryIndexReport:
    total_reports: int
    valid_reports: int
    invalid_reports: int
    reports_by_category: dict[str, list[str]]
    latest_timestamp_by_category: dict[str, str | None]
    verdict_status_distribution: dict[str, int]
    warnings_distribution: dict[str, int]
    advisory_notes: list[str]
    invalid_report_details: list[dict[str, str]] = field(default_factory=list)
    mode: str = "READ_ONLY_REPORT"
    live_trading_impact: str = "NONE"
    safety_mode: str = ADVISORY_INDEX_SAFETY_BANNER
    schema: str = "tae.advisory_index.v1"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generated_at": self.generated_at.isoformat(),
            "mode": self.mode,
            "live_trading_impact": self.live_trading_impact,
            "safety_mode": self.safety_mode,
            "total_reports": self.total_reports,
            "valid_reports": self.valid_reports,
            "invalid_reports": self.invalid_reports,
            "invalid_report_details": list(self.invalid_report_details),
            "reports_by_category": {
                key: list(self.reports_by_category.get(key, []))
                for key in ADVISORY_CATEGORIES
            },
            "latest_timestamp_by_category": dict(self.latest_timestamp_by_category),
            "verdict_status_distribution": dict(self.verdict_status_distribution),
            "warnings_distribution": dict(self.warnings_distribution),
            "advisory_notes": list(self.advisory_notes),
        }


class AdvisoryIndexBuilder:
    """Build read-only advisory index from tae_*.json files in project root."""

    def __init__(self, root: Path | str = ".") -> None:
        self._root = Path(root)

    def discover_reports(self) -> list[Path]:
        return sorted(self._root.glob("tae_*.json"))

    def _load_entry(self, path: Path) -> ReportIndexEntry:
        filename = path.name
        if filename == "tae_advisory_index.json":
            return ReportIndexEntry(
                filename=filename,
                category="unknown",
                state="skipped",
                error="Self-excluded from advisory index input",
            )

        category = categorize_report(filename)
        if not path.is_file():
            return ReportIndexEntry(
                filename=filename,
                category=category,
                state="missing",
                error="File not found",
            )

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return ReportIndexEntry(
                filename=filename,
                category=category,
                state="invalid",
                error=f"Invalid JSON: {exc}",
            )
        except OSError as exc:
            return ReportIndexEntry(
                filename=filename,
                category=category,
                state="invalid",
                error=f"Read error: {exc}",
            )

        if not isinstance(payload, dict):
            return ReportIndexEntry(
                filename=filename,
                category=category,
                state="invalid",
                error="Root element must be a JSON object",
            )

        return ReportIndexEntry(
            filename=filename,
            category=category,
            state="ok",
            timestamp=_extract_timestamp(payload),
            verdict=_extract_verdict(payload),
            warnings=_extract_warnings(payload),
        )

    def build(self) -> AdvisoryIndexReport:
        paths = self.discover_reports()
        entries = [self._load_entry(path) for path in paths]
        indexed = [entry for entry in entries if entry.state != "skipped"]

        reports_by_category: dict[str, list[str]] = {
            category: [] for category in ADVISORY_CATEGORIES
        }
        latest_by_category: dict[str, datetime | None] = {
            category: None for category in ADVISORY_CATEGORIES
        }
        verdict_counter: Counter[str] = Counter()
        warnings_counter: Counter[str] = Counter()
        invalid_details: list[dict[str, str]] = []

        valid_count = 0
        invalid_count = 0

        for entry in indexed:
            reports_by_category[entry.category].append(entry.filename)

            if entry.state == "ok":
                valid_count += 1
                if entry.verdict:
                    verdict_counter[entry.verdict] += 1
                for warning in entry.warnings:
                    warnings_counter[warning] += 1

                parsed_ts = _parse_timestamp(entry.timestamp)
                if parsed_ts is not None:
                    current = latest_by_category[entry.category]
                    if current is None or parsed_ts > current:
                        latest_by_category[entry.category] = parsed_ts
            else:
                invalid_count += 1
                invalid_details.append(
                    {
                        "report": entry.filename,
                        "state": entry.state,
                        "error": entry.error or "Unknown error",
                    }
                )
                warnings_counter[f"[{entry.state.upper()}] {entry.filename}"] += 1

        latest_timestamp_by_category = {
            category: latest.isoformat() if latest else None
            for category, latest in latest_by_category.items()
        }

        advisory_notes = self._build_advisory_notes(
            indexed=indexed,
            valid_count=valid_count,
            invalid_count=invalid_count,
            reports_by_category=reports_by_category,
            verdict_counter=verdict_counter,
            warnings_counter=warnings_counter,
        )

        return AdvisoryIndexReport(
            total_reports=len(indexed),
            valid_reports=valid_count,
            invalid_reports=invalid_count,
            reports_by_category=reports_by_category,
            latest_timestamp_by_category=latest_timestamp_by_category,
            verdict_status_distribution=dict(sorted(verdict_counter.items())),
            warnings_distribution=dict(
                sorted(warnings_counter.items(), key=lambda item: (-item[1], item[0]))
            ),
            advisory_notes=advisory_notes,
            invalid_report_details=invalid_details,
        )

    @staticmethod
    def _build_advisory_notes(
        *,
        indexed: list[ReportIndexEntry],
        valid_count: int,
        invalid_count: int,
        reports_by_category: dict[str, list[str]],
        verdict_counter: Counter[str],
        warnings_counter: Counter[str],
    ) -> list[str]:
        notes: list[str] = [
            f"Indexed {len(indexed)} canonical TAE reports from project root.",
            f"Valid JSON reports: {valid_count}; invalid or missing: {invalid_count}.",
            "Advisory index is read-only and has no live trading impact.",
        ]

        populated = [
            (category, len(reports_by_category.get(category, [])))
            for category in ADVISORY_CATEGORIES
            if reports_by_category.get(category)
        ]
        if populated:
            top = sorted(populated, key=lambda item: (-item[1], item[0]))[:5]
            summary = ", ".join(f"{cat}={count}" for cat, count in top)
            notes.append(f"Largest categories: {summary}.")

        reports_with_payload_warnings = sum(
            1 for entry in indexed if entry.state == "ok" and entry.warnings
        )
        if reports_with_payload_warnings:
            notes.append(
                f"{reports_with_payload_warnings} valid report(s) contain explicit warnings[] entries."
            )

        if verdict_counter:
            top_verdicts = verdict_counter.most_common(5)
            verdict_summary = ", ".join(f"{name}={count}" for name, count in top_verdicts)
            notes.append(f"Top verdict/status values: {verdict_summary}.")

        unknown_count = len(reports_by_category.get("unknown", []))
        if unknown_count:
            notes.append(
                f"{unknown_count} report(s) classified as unknown — review category rules if needed."
            )

        return notes
