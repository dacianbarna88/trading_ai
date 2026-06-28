"""
Regional validation report model — Phase VI Sprint B5

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Regional gap closure report for a single knowledge candidate — analysis only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER

logger = logging.getLogger(__name__)

DEFAULT_REGIONAL_JSON_PATH = Path("tae_regional_validation_kn_d5_00002.json")
DEFAULT_REGIONAL_TXT_PATH = Path("tae_regional_validation_kn_d5_00002.txt")
CANONICAL_PIPELINE_REPORT_PATH = Path("tae_strategy_evolution_daily_runner.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_regional_validation"
NOT_AVAILABLE = "NOT_AVAILABLE"
TARGET_CANDIDATE_ID = "kn_d5_00002"


class DatasetKind(str, Enum):
    HYPOTHESIS_LINKED = "HYPOTHESIS_LINKED"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    INCOMPLETE = "INCOMPLETE"
    MISSING = "MISSING"


class ReadinessProjection(str, Enum):
    NOT_READY = "NOT_READY"
    TOWARD_SANDBOX_REVIEW = "TOWARD_SANDBOX_REVIEW"
    READY_FOR_SANDBOX_REVIEW = "READY_FOR_SANDBOX_REVIEW"


@dataclass
class RegionalDatasetStatus:
    path: str
    region: str
    kind: DatasetKind
    found: bool
    row_count: int = 0
    columns_present: list[str] = field(default_factory=list)
    columns_missing: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "region": self.region,
            "kind": self.kind.value,
            "found": self.found,
            "row_count": self.row_count,
            "columns_present": list(self.columns_present),
            "columns_missing": list(self.columns_missing),
            "notes": self.notes,
        }


@dataclass
class RegionalSliceResult:
    slice_id: str
    region: str
    regime: str
    status: str
    sample_size: int = 0
    accuracy: float | None = None
    avg_forward_return: float | None = None
    data_source: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "slice_id": self.slice_id,
            "region": self.region,
            "regime": self.regime,
            "status": self.status,
            "sample_size": self.sample_size,
            "accuracy": round(self.accuracy, 4) if self.accuracy is not None else NOT_AVAILABLE,
            "avg_forward_return": (
                round(self.avg_forward_return, 4)
                if self.avg_forward_return is not None
                else NOT_AVAILABLE
            ),
            "data_source": self.data_source,
            "reason": self.reason,
        }


@dataclass
class DataAcquisitionItem:
    item_id: str
    priority: str
    description: str
    required_file: str
    required_columns: list[str]
    optional_columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "priority": self.priority,
            "description": self.description,
            "required_file": self.required_file,
            "required_columns": list(self.required_columns),
            "optional_columns": list(self.optional_columns),
        }


@dataclass
class RegionalValidationReport:
    candidate_id: str
    source_hypothesis_id: str
    title: str
    datasets_found: list[RegionalDatasetStatus]
    datasets_missing: list[RegionalDatasetStatus]
    slice_results: list[RegionalSliceResult]
    validations_completed: int
    validations_not_available: int
    us_baseline_status: str
    readiness_projection: ReadinessProjection
    readiness_rationale: str
    remaining_blockers: list[str]
    data_acquisition_checklist: list[DataAcquisitionItem]
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    pipeline_reference: dict[str, Any] | None = None
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "candidate_id": self.candidate_id,
            "source_hypothesis_id": self.source_hypothesis_id,
            "title": self.title,
            "datasets_found": [d.to_dict() for d in self.datasets_found],
            "datasets_missing": [d.to_dict() for d in self.datasets_missing],
            "slice_results": [s.to_dict() for s in self.slice_results],
            "validations_completed": self.validations_completed,
            "validations_not_available": self.validations_not_available,
            "us_baseline_status": self.us_baseline_status,
            "readiness_projection": self.readiness_projection.value,
            "readiness_rationale": self.readiness_rationale,
            "remaining_blockers": list(self.remaining_blockers),
            "data_acquisition_checklist": [i.to_dict() for i in self.data_acquisition_checklist],
            "sources_loaded": dict(self.sources_loaded),
            "pipeline_reference": self.pipeline_reference,
        }

    def format_summary(self) -> str:
        lines = [
            "===== VALIDARE REGIONALĂ TAE — PHASE VI B5 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Candidat: {self.candidate_id} ({self.title[:70]})",
            f"Hypothesis: {self.source_hypothesis_id}",
            "",
            "===== DATASET-URI REGIONALE GĂSITE =====",
        ]
        if self.datasets_found:
            for ds in self.datasets_found:
                lines.append(
                    f"  • {ds.path} [{ds.region}] — {ds.kind.value} "
                    f"(rows={ds.row_count})"
                )
                if ds.notes:
                    lines.append(f"      {ds.notes}")
        else:
            lines.append("  (niciun dataset hypothesis-linked găsit)")

        lines.extend(["", "===== DATASET-URI LIPSĂ ====="])
        for ds in self.datasets_missing:
            missing_cols = ", ".join(ds.columns_missing) if ds.columns_missing else "fișier absent"
            lines.append(f"  • {ds.path} [{ds.region}] — {missing_cols}")

        lines.extend([
            "",
            f"Validări completate: {self.validations_completed}",
            f"Validări NOT_AVAILABLE: {self.validations_not_available}",
            f"US baseline (cross-validation): {self.us_baseline_status}",
            "",
            "===== SLICE-URI REGION × REGIM =====",
        ])
        for sl in self.slice_results:
            lines.append(
                f"  {sl.slice_id}: {sl.status} "
                f"(n={sl.sample_size}, source={sl.data_source or 'none'})"
            )
            if sl.reason:
                lines.append(f"      {sl.reason}")

        lines.extend([
            "",
            f"Readiness poate avansa spre SANDBOX_REVIEW: "
            f"{'DA' if self.readiness_projection != ReadinessProjection.NOT_READY else 'NU'}",
            f"Proiecție: {self.readiness_projection.value}",
            self.readiness_rationale,
            "",
            "Blocaje rămase:",
        ])
        for blocker in self.remaining_blockers:
            lines.append(f"  • {blocker}")

        lines.extend(["", "===== CHECKLIST ACHIZIȚIE DATE ====="])
        for item in self.data_acquisition_checklist:
            lines.append(f"  [{item.priority}] {item.description}")
            lines.append(f"      Fișier: {item.required_file}")
            lines.append(f"      Coloane obligatorii: {', '.join(item.required_columns)}")

        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "RESEARCH ONLY — NO EXECUTION",
            "NOT IMPLEMENTED — validare regională analitică only",
            "Nu se estimează valori lipsă — doar NOT_AVAILABLE.",
            "",
            "No live trading files were modified.",
            "",
        ])
        return "\n".join(lines)


class RegionalValidationStore:
    """JSON/TXT persistence — stdlib only."""

    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_REGIONAL_JSON_PATH
        self._txt_path = txt_path or DEFAULT_REGIONAL_TXT_PATH

    def persist(self, report: RegionalValidationReport) -> Path:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: RegionalValidationReport) -> Path:
        self._txt_path.write_text(report.format_summary() + "\n", encoding="utf-8")
        return self._txt_path
