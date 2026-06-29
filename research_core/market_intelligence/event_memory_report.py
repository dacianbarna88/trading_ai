"""
Event memory report — Phase X Sprint X.6A

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.market_intelligence.event_schema import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_NAME,
    TAE_VERSION,
)

DEFAULT_JSON_PATH = Path("tae_event_memory.json")
DEFAULT_TXT_PATH = Path("tae_event_memory.txt")
EVENT_MEMORY_SAFETY_BANNER = (
    "ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE"
)


class EventMemoryVerdict(str, Enum):
    EVENT_MEMORY_SCAFFOLD_READY = "EVENT_MEMORY_SCAFFOLD_READY"
    EVENT_MEMORY_SCAFFOLD_READY_WITH_WARNINGS = "EVENT_MEMORY_SCAFFOLD_READY_WITH_WARNINGS"
    EVENT_MEMORY_SCHEMA_FAILED = "EVENT_MEMORY_SCHEMA_FAILED"


@dataclass
class EventMemoryReport:
    verdict: EventMemoryVerdict
    event_count: int
    schema_validation_passed: bool
    round_trip_passed: bool
    schema_version: int
    registry: dict[str, Any]
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safety_mode: str = EVENT_MEMORY_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.registry)
        payload.update(
            {
                "version": CURRENT_SCHEMA_VERSION,
                "schema": SCHEMA_NAME,
                "generated_at": self.generated_at.isoformat(),
                "safety_mode": self.safety_mode,
                "verdict": self.verdict.value,
                "event_count": self.event_count,
                "schema_validation_passed": self.schema_validation_passed,
                "round_trip_passed": self.round_trip_passed,
                "tae_version": TAE_VERSION,
                "validation_errors": list(self.validation_errors),
                "warnings": list(self.warnings),
            }
        )
        return payload

    def format_text(self) -> str:
        lines = [
            "===== TAE EVENT MEMORY — SPRINT X.6A =====",
            "",
            f"Safety banner: {self.safety_mode}",
            "Mode: SCHEMA_SCAFFOLD_ONLY | NO_INGESTION | NO_MODELS | NO_WIRING",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            "===== REGISTRY =====",
            f"  Schema: {SCHEMA_NAME}",
            f"  Schema version: {self.schema_version}",
            f"  TAE version: {TAE_VERSION}",
            f"  Events stored: {self.event_count}",
            f"  Schema validation passed: {self.schema_validation_passed}",
            f"  Round-trip passed: {self.round_trip_passed}",
            f"  Public data attestation: {self.registry.get('public_data_attestation')}",
            f"  MNPI excluded: {self.registry.get('mnpi_excluded')}",
            "",
            "===== METADATA REQUIREMENTS =====",
            "  Every object includes: created_at, updated_at, schema_version, source_module, tae_version",
            "  Event IDs are immutable; revisions use supersedes_event_id (future phases)",
            "  Forward-compatible schemas; deprecation via schema_version only",
            "",
            "===== SCOPE =====",
            "  Built: event schema, empty memory store, validation, demo",
            "  Not built: ingestion, live news, models, meta/runtime wiring",
        ]

        if self.validation_errors:
            lines.extend(["", "===== VALIDATION ERRORS ====="])
            for error in self.validation_errors:
                lines.append(f"  • {error}")

        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")

        return "\n".join(lines)


class EventMemoryReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: EventMemoryReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
