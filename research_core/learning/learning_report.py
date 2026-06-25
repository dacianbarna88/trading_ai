"""
Learning report model — Sprint 5.4

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Structured meta-learning output from experiment history — not trading signals.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER

logger = logging.getLogger(__name__)

DEFAULT_REPORT_PATH = Path("tae_learning_report.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_learning_report"


@dataclass
class LearningReport:
    experiments_analyzed: int
    average_accuracy: float
    average_forward_return: float
    best_organism: str
    strongest_hypothesis_family: str
    strongest_regime: str
    knowledge_candidates_count: int
    learning_confidence: float
    key_lessons_learned: list[str]
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    best_organism_trust_score: float = 0.0
    top_quality_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "experiments_analyzed": self.experiments_analyzed,
            "average_accuracy": round(self.average_accuracy, 4),
            "average_forward_return": round(self.average_forward_return, 4),
            "best_organism": self.best_organism,
            "best_organism_trust_score": round(self.best_organism_trust_score, 2),
            "strongest_hypothesis_family": self.strongest_hypothesis_family,
            "strongest_regime": self.strongest_regime,
            "knowledge_candidates_count": self.knowledge_candidates_count,
            "learning_confidence": round(self.learning_confidence, 2),
            "top_quality_score": round(self.top_quality_score, 2),
            "key_lessons_learned": list(self.key_lessons_learned),
            "sources_loaded": dict(self.sources_loaded),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LearningReport | None:
        try:
            generated = data.get("generated_at")
            if generated:
                dt = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            lessons = data.get("key_lessons_learned", [])
            if not isinstance(lessons, list):
                lessons = []

            sources = data.get("sources_loaded", {})
            if not isinstance(sources, dict):
                sources = {}

            return cls(
                experiments_analyzed=int(data.get("experiments_analyzed", 0)),
                average_accuracy=float(data.get("average_accuracy", 0)),
                average_forward_return=float(data.get("average_forward_return", 0)),
                best_organism=str(data.get("best_organism", "")),
                strongest_hypothesis_family=str(data.get("strongest_hypothesis_family", "")),
                strongest_regime=str(data.get("strongest_regime", "")),
                knowledge_candidates_count=int(data.get("knowledge_candidates_count", 0)),
                learning_confidence=float(data.get("learning_confidence", 0)),
                key_lessons_learned=[str(l) for l in lessons],
                safety_mode=str(data.get("safety_mode", RESEARCH_SAFETY_BANNER)),
                generated_at=dt,
                sources_loaded={str(k): bool(v) for k, v in sources.items()},
                best_organism_trust_score=float(data.get("best_organism_trust_score", 0)),
                top_quality_score=float(data.get("top_quality_score", 0)),
            )
        except (TypeError, ValueError):
            return None

    def format_summary(self) -> str:
        lines = [
            "===== TAE LEARNING REPORT =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Experiments analyzed: {self.experiments_analyzed}",
            f"Average accuracy: {self.average_accuracy:.2%}",
            f"Average forward return: {self.average_forward_return:.4f}%",
            f"Best organism: {self.best_organism} (trust={self.best_organism_trust_score:.1f})",
            f"Strongest hypothesis family: {self.strongest_hypothesis_family}",
            f"Strongest regime: {self.strongest_regime}",
            f"Knowledge candidates: {self.knowledge_candidates_count}",
            f"Learning confidence: {self.learning_confidence:.1f}/100",
            f"Top quality score observed: {self.top_quality_score:.2f}",
            "",
            "Sources loaded:",
        ]
        for name, ok in sorted(self.sources_loaded.items()):
            lines.append(f"  {name}: {'yes' if ok else 'no'}")
        lines.append("")
        lines.append("Key lessons learned:")
        if not self.key_lessons_learned:
            lines.append("  (none)")
        else:
            for idx, lesson in enumerate(self.key_lessons_learned, start=1):
                lines.append(f"  {idx}. {lesson}")
        lines.append("")
        return "\n".join(lines)


class LearningReportStore:
    """JSON persistence for learning reports."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_REPORT_PATH
        self._report: LearningReport | None = None
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def loaded_at_startup(self) -> bool:
        return self._loaded_at_startup

    @property
    def report(self) -> LearningReport | None:
        return self._report

    def set_report(self, report: LearningReport) -> None:
        self._report = report

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Learning report unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict):
            return False
        if payload.get("schema") != SCHEMA_NAME:
            return False

        report = LearningReport.from_dict(payload)
        if report is None:
            return False
        self._report = report
        return True

    def persist(self, report: LearningReport | None = None) -> Path:
        if report is not None:
            self._report = report
        if self._report is None:
            raise ValueError("No learning report to persist.")
        self._path.write_text(
            json.dumps(self._report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path
