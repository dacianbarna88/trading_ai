"""
TAE Evidence Engine report — Phase VII foundation

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_JSON_PATH = Path("tae_evidence_engine_report.json")
DEFAULT_TXT_PATH = Path("tae_evidence_engine_report.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_evidence_engine_report"
CANONICAL_REGISTRY_SOURCE = "evidence_engine_registry"
SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class EvidenceStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"


class EvidenceRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    HIGHER = "HIGHER"


class ImplementationEligibility(str, Enum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    PAPER_VALIDATION_ELIGIBLE = "PAPER_VALIDATION_ELIGIBLE"
    DEPLOYMENT_CANDIDATE = "DEPLOYMENT_CANDIDATE"


class EvidenceEngineVerdict(str, Enum):
    EVIDENCE_ENGINE_INITIALIZED = "EVIDENCE_ENGINE_INITIALIZED"
    EVIDENCE_ENGINE_SOURCE_OF_TRUTH_ALIGNED = "EVIDENCE_ENGINE_SOURCE_OF_TRUTH_ALIGNED"
    EVIDENCE_CONTRADICTION_DETECTED = "EVIDENCE_CONTRADICTION_DETECTED"


@dataclass
class EvidenceContradiction:
    evidence_id: str
    metric: str
    source_file: str
    expected_value: Any
    actual_value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "metric": self.metric,
            "source_file": self.source_file,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
        }


@dataclass
class EvidenceItem:
    evidence_id: str
    title: str
    conclusion: str
    source_phase: str
    source_ref: str
    status: EvidenceStatus
    risk_level: EvidenceRiskLevel
    implementation_eligibility: ImplementationEligibility
    supporting_metrics: dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "title": self.title,
            "conclusion": self.conclusion,
            "source_phase": self.source_phase,
            "source_ref": self.source_ref,
            "status": self.status.value,
            "risk_level": self.risk_level.value,
            "implementation_eligibility": self.implementation_eligibility.value,
            "supporting_metrics": dict(self.supporting_metrics),
            "registered_at": self.registered_at.isoformat(),
        }


@dataclass
class EvidenceEngineReport:
    verdict: EvidenceEngineVerdict
    evidence_items: list[EvidenceItem]
    confirmed_count: int
    inconclusive_count: int
    rejected_count: int
    registry_item_count: int
    data_source_flags: list[str] = field(default_factory=list)
    contradictions: list[EvidenceContradiction] = field(default_factory=list)
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    evidence_gap_registration: dict[str, Any] | None = None
    confidence_registration: dict[str, Any] | None = None
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "canonical_registry_source": CANONICAL_REGISTRY_SOURCE,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "registry_item_count": self.registry_item_count,
            "confirmed_count": self.confirmed_count,
            "inconclusive_count": self.inconclusive_count,
            "rejected_count": self.rejected_count,
            "data_source_flags": list(self.data_source_flags),
            "contradictions": [c.to_dict() for c in self.contradictions],
            "sources_loaded": dict(self.sources_loaded),
            "evidence_gap_registration": dict(self.evidence_gap_registration)
            if self.evidence_gap_registration
            else None,
            "confidence_registration": dict(self.confidence_registration)
            if self.confidence_registration
            else None,
            "evidence_items": [item.to_dict() for item in self.evidence_items],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE EVIDENCE ENGINE — REGISTRU CENTRAL =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Elemente înregistrate: {self.registry_item_count}",
            f"  CONFIRMED: {self.confirmed_count} | "
            f"INCONCLUSIVE: {self.inconclusive_count} | "
            f"REJECTED: {self.rejected_count}",
        ]
        if self.data_source_flags:
            lines.append(f"Data source flags: {', '.join(self.data_source_flags)}")
        if self.sources_loaded:
            lines.append("Surse JSON încărcate:")
            for name, loaded in sorted(self.sources_loaded.items()):
                lines.append(f"  {name}: {'yes' if loaded else 'no'}")
        if self.evidence_gap_registration:
            gap = self.evidence_gap_registration
            lines.extend([
                "",
                "===== EVIDENCE GAP REGISTRATION =====",
                f"  evidence_gap_registered: {gap.get('evidence_gap_registered')}",
                f"  evidence_gap_status: {gap.get('evidence_gap_status')}",
                f"  evidence_gap_source_report: {gap.get('evidence_gap_source_report')}",
                f"  evidence_gap_last_loaded: {gap.get('evidence_gap_last_loaded')}",
                f"  evidence_gap_warning_count: {gap.get('evidence_gap_warning_count')}",
            ])
        if self.confidence_registration:
            conf = self.confidence_registration
            report = conf.get("confidence_report") or {}
            lines.extend([
                "",
                "===== CONFIDENCE REGISTRATION =====",
                f"  confidence_registered: {conf.get('confidence_registered')}",
                f"  confidence_status: {conf.get('confidence_status')}",
                f"  confidence_source: {conf.get('confidence_source')}",
                f"  confidence_last_refresh: {conf.get('confidence_last_refresh')}",
                f"  confidence_report.candidates_recalibrated: "
                f"{report.get('candidates_recalibrated')}",
                f"  confidence_report.top_candidate_after: "
                f"{report.get('top_candidate_after')}",
            ])
        if self.contradictions:
            lines.extend(["", "Contradicții detectate:"])
            for c in self.contradictions:
                lines.append(
                    f"  [{c.evidence_id}] {c.metric}: "
                    f"expected {c.expected_value} vs actual {c.actual_value} "
                    f"({c.source_file})"
                )
        lines.extend(["", "===== ELEMENTE DE EVIDENȚĂ ====="])
        for item in self.evidence_items:
            lines.extend([
                f"--- {item.evidence_id} ---",
                f"  Titlu: {item.title}",
                f"  Status: {item.status.value}",
                f"  Risc: {item.risk_level.value}",
                f"  Eligibilitate implementare: {item.implementation_eligibility.value}",
                f"  Sursă: {item.source_phase} ({item.source_ref})",
                f"  Concluzie: {item.conclusion}",
            ])
            if item.supporting_metrics:
                lines.append("  Metrici:")
                for key, value in item.supporting_metrics.items():
                    lines.append(f"    {key}: {value}")
            lines.append("")
        lines.extend([
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Fără instrucțiuni BUY/SELL — infrastructură research read-only.",
            "",
        ])
        return "\n".join(lines)


class EvidenceReportStore:
    """Persists EvidenceEngineReport — serializes Evidence Registry state."""

    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def from_registry(self, registry: Any) -> Path:
        """Serialize registry state to canonical JSON report."""
        report = registry.build_report()
        self.persist(report)
        self.persist_txt(report)
        return self._json_path

    def load(self) -> dict[str, Any] | None:
        if not self._json_path.is_file():
            return None
        try:
            payload = json.loads(self._json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load evidence report %s: %s", self._json_path, exc)
            return None
        return payload if isinstance(payload, dict) else None

    def persist(self, report: EvidenceEngineReport) -> Path:
        self._json_path.write_text(
            json.dumps(
                report.to_dict(),
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: EvidenceEngineReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
