"""
Evidence record model — Phase VI Sprint B2

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Persistent evidence history for knowledge candidates — tracking only.
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

DEFAULT_HISTORY_JSON_PATH = Path("tae_evidence_history.json")
DEFAULT_HISTORY_TXT_PATH = Path("tae_evidence_history.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_evidence_history"
NOT_AVAILABLE = "NOT_AVAILABLE"


class EvidenceRecordType(str, Enum):
    EXPERIMENT_RESULT = "EXPERIMENT_RESULT"
    QUALITY_RANKING = "QUALITY_RANKING"
    CROSS_VALIDATION = "CROSS_VALIDATION"
    LEARNING_SUPPORT = "LEARNING_SUPPORT"
    STRATEGY_RECOMMENDATION = "STRATEGY_RECOMMENDATION"
    EVOLUTION_PLAN = "EVOLUTION_PLAN"
    IMPLEMENTATION_PATCH = "IMPLEMENTATION_PATCH"
    PATCH_REVIEW = "PATCH_REVIEW"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    CANONICAL_REGISTRY = "CANONICAL_REGISTRY"


class EvidencePolarity(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    MISSING = "MISSING"
    NEUTRAL = "NEUTRAL"


class ConfidenceTrend(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    WEAKENING = "WEAKENING"
    UNKNOWN = "UNKNOWN"


class ImplementationReadiness(str, Enum):
    NOT_READY = "NOT_READY"
    READY_FOR_SANDBOX_REVIEW = "READY_FOR_SANDBOX_REVIEW"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"


@dataclass
class EvidenceRecord:
    record_id: str
    record_type: EvidenceRecordType
    source_ref: str
    summary: str
    polarity: EvidencePolarity
    score_contribution: float = 0.0
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.record_type, str):
            self.record_type = EvidenceRecordType(self.record_type)
        if isinstance(self.polarity, str):
            self.polarity = EvidencePolarity(self.polarity)

    @property
    def fingerprint(self) -> str:
        return f"{self.record_type.value}:{self.source_ref}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type.value,
            "source_ref": self.source_ref,
            "summary": self.summary,
            "polarity": self.polarity.value,
            "score_contribution": round(self.score_contribution, 2),
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceRecord | None:
        try:
            rec_type = str(data.get("record_type", EvidenceRecordType.EXPERIMENT_RESULT.value))
            try:
                record_type = EvidenceRecordType(rec_type)
            except ValueError:
                record_type = EvidenceRecordType.EXPERIMENT_RESULT

            polarity_raw = str(data.get("polarity", EvidencePolarity.NEUTRAL.value))
            try:
                polarity = EvidencePolarity(polarity_raw)
            except ValueError:
                polarity = EvidencePolarity.NEUTRAL

            recorded = data.get("recorded_at")
            if recorded:
                dt = datetime.fromisoformat(str(recorded).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            return cls(
                record_id=str(data.get("record_id", "")),
                record_type=record_type,
                source_ref=str(data.get("source_ref", "")),
                summary=str(data.get("summary", "")),
                polarity=polarity,
                score_contribution=float(data.get("score_contribution", 0)),
                recorded_at=dt,
            )
        except (TypeError, ValueError):
            return None


@dataclass
class EvidenceDossier:
    candidate_id: str
    source_hypothesis_id: str
    title: str
    evidence_records: list[EvidenceRecord]
    total_evidence_count: int
    positive_evidence_count: int
    negative_evidence_count: int
    missing_evidence_count: int
    current_evidence_score: float
    confidence_trend: ConfidenceTrend
    implementation_readiness: ImplementationReadiness
    blockers: list[str]
    next_required_evidence: list[str]
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    safety_mode: str = RESEARCH_SAFETY_BANNER

    def __post_init__(self) -> None:
        if isinstance(self.confidence_trend, str):
            self.confidence_trend = ConfidenceTrend(self.confidence_trend)
        if isinstance(self.implementation_readiness, str):
            self.implementation_readiness = ImplementationReadiness(self.implementation_readiness)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_hypothesis_id": self.source_hypothesis_id,
            "title": self.title,
            "evidence_records": [r.to_dict() for r in self.evidence_records],
            "total_evidence_count": self.total_evidence_count,
            "positive_evidence_count": self.positive_evidence_count,
            "negative_evidence_count": self.negative_evidence_count,
            "missing_evidence_count": self.missing_evidence_count,
            "current_evidence_score": round(self.current_evidence_score, 2),
            "confidence_trend": self.confidence_trend.value,
            "implementation_readiness": self.implementation_readiness.value,
            "blockers": list(self.blockers),
            "next_required_evidence": list(self.next_required_evidence),
            "last_updated": self.last_updated.isoformat(),
            "safety_mode": self.safety_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceDossier | None:
        try:
            records_raw = data.get("evidence_records", [])
            records: list[EvidenceRecord] = []
            if isinstance(records_raw, list):
                for item in records_raw:
                    if isinstance(item, dict):
                        rec = EvidenceRecord.from_dict(item)
                        if rec is not None:
                            records.append(rec)

            trend = str(data.get("confidence_trend", ConfidenceTrend.UNKNOWN.value))
            try:
                confidence_trend = ConfidenceTrend(trend)
            except ValueError:
                confidence_trend = ConfidenceTrend.UNKNOWN

            readiness = str(
                data.get("implementation_readiness", ImplementationReadiness.NOT_READY.value)
            )
            try:
                implementation_readiness = ImplementationReadiness(readiness)
            except ValueError:
                implementation_readiness = ImplementationReadiness.NOT_READY

            updated = data.get("last_updated")
            if updated:
                dt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            blockers = data.get("blockers", [])
            next_req = data.get("next_required_evidence", [])
            if not isinstance(blockers, list):
                blockers = []
            if not isinstance(next_req, list):
                next_req = []

            return cls(
                candidate_id=str(data["candidate_id"]),
                source_hypothesis_id=str(data.get("source_hypothesis_id", "")),
                title=str(data.get("title", "")),
                evidence_records=records,
                total_evidence_count=int(data.get("total_evidence_count", len(records))),
                positive_evidence_count=int(data.get("positive_evidence_count", 0)),
                negative_evidence_count=int(data.get("negative_evidence_count", 0)),
                missing_evidence_count=int(data.get("missing_evidence_count", 0)),
                current_evidence_score=float(data.get("current_evidence_score", 0)),
                confidence_trend=confidence_trend,
                implementation_readiness=implementation_readiness,
                blockers=[str(b) for b in blockers],
                next_required_evidence=[str(n) for n in next_req],
                last_updated=dt,
                safety_mode=str(data.get("safety_mode", RESEARCH_SAFETY_BANNER)),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass
class EvidenceHistoryReport:
    candidates_analyzed: int
    dossiers_created: int
    dossiers_updated: int
    dossiers: list[EvidenceDossier]
    top_evidence_score: float
    weakest_evidence_score: float
    sandbox_ready_count: int
    blocked_count: int
    main_blockers: list[str]
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    canonical_reference: dict[str, Any] | None = None
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "candidates_analyzed": self.candidates_analyzed,
            "dossiers_created": self.dossiers_created,
            "dossiers_updated": self.dossiers_updated,
            "top_evidence_score": round(self.top_evidence_score, 2),
            "weakest_evidence_score": round(self.weakest_evidence_score, 2),
            "sandbox_ready_count": self.sandbox_ready_count,
            "blocked_count": self.blocked_count,
            "main_blockers": list(self.main_blockers),
            "sources_loaded": dict(self.sources_loaded),
            "canonical_reference": self.canonical_reference,
            "dossiers": [d.to_dict() for d in self.dossiers],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE EVIDENCE HISTORY =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Candidates analyzed: {self.candidates_analyzed}",
            f"Dossiers created (this run): {self.dossiers_created}",
            f"Dossiers updated (this run): {self.dossiers_updated}",
            f"Top evidence score: {self.top_evidence_score:.1f}",
            f"Weakest evidence score: {self.weakest_evidence_score:.1f}",
            f"Ready for sandbox review: {self.sandbox_ready_count}",
            f"Blocked (NOT_READY): {self.blocked_count}",
            "",
            "Main blockers:",
        ]
        for b in self.main_blockers:
            lines.append(f"  - {b}")
        lines.append("")
        lines.append("===== DOSSIER SUMMARY =====")
        for dossier in sorted(self.dossiers, key=lambda d: d.current_evidence_score, reverse=True):
            lines.extend([
                "----------------------------------------",
                f"{dossier.candidate_id} | score={dossier.current_evidence_score:.1f} | "
                f"trend={dossier.confidence_trend.value} | "
                f"readiness={dossier.implementation_readiness.value}",
                f"  title: {dossier.title[:80]}",
                f"  evidence: +{dossier.positive_evidence_count} / "
                f"-{dossier.negative_evidence_count} / "
                f"missing={dossier.missing_evidence_count} (total={dossier.total_evidence_count})",
            ])
            if dossier.blockers:
                lines.append(f"  blockers: {'; '.join(dossier.blockers[:3])}")
            if dossier.next_required_evidence:
                lines.append(f"  next: {dossier.next_required_evidence[0][:100]}")
            lines.append("")
        lines.extend([
            "===== AVERTISMENT =====",
            "NOT IMPLEMENTED — EVIDENCE TRACKING ONLY",
            "",
            "===== CONFIRMARE SIGURANȚĂ =====",
            "No live trading files were modified",
            "",
            "Urmărire evidențe — nu modifică strategie sau execuție.",
            "",
        ])
        return "\n".join(lines)


class EvidenceHistoryStore:
    """JSON persistence for evidence dossiers — stdlib only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_HISTORY_JSON_PATH
        self._dossiers: dict[str, EvidenceDossier] = {}
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    def get(self, candidate_id: str) -> EvidenceDossier | None:
        return self._dossiers.get(candidate_id)

    def list_all(self) -> list[EvidenceDossier]:
        return sorted(self._dossiers.values(), key=lambda d: d.candidate_id)

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Evidence history unreadable (%s): %s", self._path, exc)
            return False
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            return False
        items = payload.get("dossiers", [])
        if not isinstance(items, list):
            return False
        self._dossiers.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            dossier = EvidenceDossier.from_dict(item)
            if dossier is not None:
                self._dossiers[dossier.candidate_id] = dossier
        return True

    def upsert_dossier(self, dossier: EvidenceDossier, merge_records: bool = True) -> bool:
        """Insert or update dossier. merge_records avoids duplicate evidence fingerprints."""
        existing = self._dossiers.get(dossier.candidate_id)
        if existing is None:
            self._dossiers[dossier.candidate_id] = dossier
            return True

        if not merge_records:
            self._dossiers[dossier.candidate_id] = dossier
            return False

        seen = {r.fingerprint for r in existing.evidence_records}
        merged_records = list(existing.evidence_records)
        for record in dossier.evidence_records:
            if record.fingerprint not in seen:
                merged_records.append(record)
                seen.add(record.fingerprint)

        dossier.evidence_records = merged_records
        dossier.total_evidence_count = len(merged_records)
        dossier.positive_evidence_count = sum(
            1 for r in merged_records if r.polarity == EvidencePolarity.POSITIVE
        )
        dossier.negative_evidence_count = sum(
            1 for r in merged_records if r.polarity == EvidencePolarity.NEGATIVE
        )
        dossier.missing_evidence_count = sum(
            1 for r in merged_records if r.polarity == EvidencePolarity.MISSING
        )
        self._dossiers[dossier.candidate_id] = dossier
        return False

    def persist(self, report: EvidenceHistoryReport) -> Path:
        payload = report.to_dict()
        payload["dossiers"] = [d.to_dict() for d in self.list_all()]
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def persist_txt(self, report: EvidenceHistoryReport) -> Path:
        DEFAULT_HISTORY_TXT_PATH.write_text(report.format_text() + "\n", encoding="utf-8")
        return DEFAULT_HISTORY_TXT_PATH
