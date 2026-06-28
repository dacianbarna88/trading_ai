"""
Recommendation Outcome Report — Phase X Sprint X.2C

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | LEARNING_ONLY
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

DEFAULT_JSON_PATH = Path("tae_recommendation_outcome.json")
DEFAULT_TXT_PATH = Path("tae_recommendation_outcome.txt")
REGISTRY_JSON_PATH = Path("tae_recommendation_outcome_registry.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_recommendation_outcome"
REGISTRY_SCHEMA = "tae_recommendation_outcome_registry"


class RecommendationOutcomeVerdict(str, Enum):
    RECOMMENDATION_OUTCOME_READY = "RECOMMENDATION_OUTCOME_READY"
    RECOMMENDATION_OUTCOME_READY_WITH_WARNINGS = (
        "RECOMMENDATION_OUTCOME_READY_WITH_WARNINGS"
    )
    RECOMMENDATION_OUTCOME_INSUFFICIENT_HISTORY = (
        "RECOMMENDATION_OUTCOME_INSUFFICIENT_HISTORY"
    )


class RecommendationOutcomeStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    NO_EVIDENCE_YET = "NO_EVIDENCE_YET"
    FAILED = "FAILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class RecommendationOutcomeEntry:
    recommendation_id: str
    category: str
    target_strategy_or_module: str
    outcome: str
    original_confidence_score: float
    recommendation_quality: float
    evidence_strength: float
    learning_confidence: float
    issued_at: str
    last_evaluated_at: str
    recommendation_age_days: float
    baseline_metrics: dict[str, Any]
    current_metrics: dict[str, Any]
    outcome_rationale: str
    evidence_sources: list[str] = field(default_factory=list)
    evaluation_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "category": self.category,
            "target_strategy_or_module": self.target_strategy_or_module,
            "outcome": self.outcome,
            "original_confidence_score": round(self.original_confidence_score, 4),
            "recommendation_quality": round(self.recommendation_quality, 4),
            "evidence_strength": round(self.evidence_strength, 4),
            "learning_confidence": round(self.learning_confidence, 4),
            "issued_at": self.issued_at,
            "last_evaluated_at": self.last_evaluated_at,
            "recommendation_age_days": round(self.recommendation_age_days, 2),
            "baseline_metrics": dict(self.baseline_metrics),
            "current_metrics": dict(self.current_metrics),
            "outcome_rationale": self.outcome_rationale,
            "evidence_sources": list(self.evidence_sources),
            "evaluation_count": self.evaluation_count,
        }


@dataclass
class RecommendationOutcomeReport:
    verdict: RecommendationOutcomeVerdict
    recommendation_history: list[RecommendationOutcomeEntry]
    recommendation_statistics: dict[str, Any]
    category_accuracy: dict[str, float]
    average_recommendation_confidence: float
    improvement_trend: str
    false_recommendation_count: int
    recommendation_aging: dict[str, Any]
    learning_metrics: dict[str, Any]
    sources_loaded: dict[str, bool]
    sources_loaded_count: int
    registry_evaluation_cycles: int
    warnings: list[str] = field(default_factory=list)
    protected_files_unchanged: bool = True
    learning_only: bool = True
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "learning_only": self.learning_only,
            "verdict": self.verdict.value,
            "sources_loaded": dict(self.sources_loaded),
            "sources_loaded_count": self.sources_loaded_count,
            "registry_evaluation_cycles": self.registry_evaluation_cycles,
            "recommendation_history": [
                entry.to_dict() for entry in self.recommendation_history
            ],
            "recommendation_statistics": dict(self.recommendation_statistics),
            "category_accuracy": dict(self.category_accuracy),
            "average_recommendation_confidence": round(
                self.average_recommendation_confidence, 4
            ),
            "improvement_trend": self.improvement_trend,
            "false_recommendation_count": self.false_recommendation_count,
            "recommendation_aging": dict(self.recommendation_aging),
            "learning_metrics": dict(self.learning_metrics),
            "warnings": list(self.warnings),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        stats = self.recommendation_statistics
        learning = self.learning_metrics
        lines = [
            "===== TAE RECOMMENDATION OUTCOME LEARNING — SPRINT X.2C =====",
            "",
            f"Safety banner: {self.safety_mode}",
            f"Mode: LEARNING_ONLY",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            f"Registry evaluation cycles: {self.registry_evaluation_cycles}",
            f"Canonical inputs loaded: {self.sources_loaded_count}/{len(self.sources_loaded)}",
            "",
            "===== LEARNING METRICS =====",
            f"  Recommendation quality: {learning.get('recommendation_quality')}",
            f"  Recommendation accuracy: {learning.get('recommendation_accuracy')}",
            f"  Evidence strength: {learning.get('evidence_strength')}",
            f"  Learning confidence: {learning.get('learning_confidence')}",
            f"  Historical recommendation score: {learning.get('historical_recommendation_score')}",
            "",
            "===== STATISTICS =====",
            f"  Total evaluated: {stats.get('total_evaluated')}",
            f"  Outcome counts: {stats.get('outcome_counts')}",
            f"  Average confidence: {self.average_recommendation_confidence:.4f}",
            f"  False recommendations: {self.false_recommendation_count}",
            f"  Improvement trend: {self.improvement_trend}",
            "",
            "===== CATEGORY ACCURACY =====",
        ]
        for category, accuracy in sorted(self.category_accuracy.items()):
            lines.append(f"  {category}: {accuracy:.4f}")
        lines.extend([
            "",
            "===== RECOMMENDATION AGING =====",
            f"  Average age (days): {self.recommendation_aging.get('average_age_days')}",
            f"  Oldest (days): {self.recommendation_aging.get('oldest_days')}",
            f"  Newest (days): {self.recommendation_aging.get('newest_days')}",
            "",
            "===== RECOMMENDATION HISTORY =====",
        ])
        for entry in self.recommendation_history:
            lines.extend([
                f"[{entry.recommendation_id}] {entry.category} → {entry.target_strategy_or_module}",
                f"  Outcome: {entry.outcome} | Quality: {entry.recommendation_quality:.4f}",
                f"  Age: {entry.recommendation_age_days:.1f}d | Evaluations: {entry.evaluation_count}",
                f"  Rationale: {entry.outcome_rationale}",
                "",
            ])
        lines.extend(["===== CANONICAL INPUTS ====="])
        for name, loaded in self.sources_loaded.items():
            lines.append(f"  • {name}: {'loaded' if loaded else 'missing'}")
        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")
        lines.append("")
        return "\n".join(lines)


class RecommendationOutcomeReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: RecommendationOutcomeReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path


def load_outcome_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "version": 1,
            "schema": REGISTRY_SCHEMA,
            "evaluation_cycles": 0,
            "entries": {},
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "version": 1,
            "schema": REGISTRY_SCHEMA,
            "evaluation_cycles": 0,
            "entries": {},
        }
    if not isinstance(data, dict):
        return {"version": 1, "schema": REGISTRY_SCHEMA, "evaluation_cycles": 0, "entries": {}}
    if not isinstance(data.get("entries"), dict):
        data["entries"] = {}
    return data


def persist_outcome_registry(path: Path, registry: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
