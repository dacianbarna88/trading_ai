"""
Meta Evolution Report — Phase X Sprint X.2B

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | RECOMMENDATION_ONLY
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

DEFAULT_JSON_PATH = Path("tae_meta_evolution.json")
DEFAULT_TXT_PATH = Path("tae_meta_evolution.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_meta_evolution"
ALLOWED_ACTION = "REVIEW_ONLY"


class MetaEvolutionVerdict(str, Enum):
    META_EVOLUTION_READY = "META_EVOLUTION_READY"
    META_EVOLUTION_READY_WITH_WARNINGS = "META_EVOLUTION_READY_WITH_WARNINGS"
    META_EVOLUTION_INSUFFICIENT_DATA = "META_EVOLUTION_INSUFFICIENT_DATA"


class RecommendationCategory(str, Enum):
    PROMOTE_CANDIDATE = "PROMOTE_CANDIDATE"
    CONTINUE_PAPER_TRACKING = "CONTINUE_PAPER_TRACKING"
    RETIRE_OR_FREEZE_CANDIDATE = "RETIRE_OR_FREEZE_CANDIDATE"
    LAUNCH_NEW_EXPERIMENT = "LAUNCH_NEW_EXPERIMENT"
    INVESTIGATE_UNDERPERFORMANCE = "INVESTIGATE_UNDERPERFORMANCE"
    IMPROVE_DATA_QUALITY = "IMPROVE_DATA_QUALITY"
    NO_ACTION = "NO_ACTION"


@dataclass
class EvolutionRecommendation:
    recommendation_id: str
    category: str
    target_strategy_or_module: str
    evidence_sources: list[str]
    confidence_score: float
    rationale: str
    risk_level: str
    required_human_review: bool
    allowed_action: str = ALLOWED_ACTION

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "category": self.category,
            "target_strategy_or_module": self.target_strategy_or_module,
            "evidence_sources": list(self.evidence_sources),
            "confidence_score": round(self.confidence_score, 4),
            "rationale": self.rationale,
            "risk_level": self.risk_level,
            "required_human_review": self.required_human_review,
            "allowed_action": self.allowed_action,
        }


@dataclass
class MetaEvolutionReport:
    verdict: MetaEvolutionVerdict
    recommendations: list[EvolutionRecommendation]
    sources_loaded: dict[str, bool]
    sources_loaded_count: int
    meta_intelligence_verdict: str | None
    recommendation_summary: dict[str, int]
    warnings: list[str] = field(default_factory=list)
    protected_files_unchanged: bool = True
    safety_mode: str = SAFETY_BANNER
    recommendation_only: bool = True
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "recommendation_only": self.recommendation_only,
            "allowed_action": ALLOWED_ACTION,
            "verdict": self.verdict.value,
            "meta_intelligence_verdict": self.meta_intelligence_verdict,
            "sources_loaded": dict(self.sources_loaded),
            "sources_loaded_count": self.sources_loaded_count,
            "recommendation_summary": dict(self.recommendation_summary),
            "recommendations": [rec.to_dict() for rec in self.recommendations],
            "warnings": list(self.warnings),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE META EVOLUTION — SPRINT X.2B =====",
            "",
            f"Safety banner: {self.safety_mode}",
            f"Mode: RECOMMENDATION_ONLY — {ALLOWED_ACTION}",
            f"Verdict: {self.verdict.value}",
            f"Meta Intelligence verdict: {self.meta_intelligence_verdict or 'N/A'}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            f"Canonical inputs loaded: {self.sources_loaded_count}/{len(self.sources_loaded)}",
            "",
            "===== RECOMMENDATION SUMMARY =====",
        ]
        for category, count in sorted(self.recommendation_summary.items()):
            lines.append(f"  {category}: {count}")
        lines.extend(["", "===== EVOLUTION RECOMMENDATIONS =====", ""])
        if not self.recommendations:
            lines.append("  (none)")
        for rec in self.recommendations:
            lines.extend([
                f"[{rec.recommendation_id}] {rec.category}",
                f"  Target: {rec.target_strategy_or_module}",
                f"  Confidence: {rec.confidence_score:.4f} | Risk: {rec.risk_level}",
                f"  Human review required: {rec.required_human_review}",
                f"  Allowed action: {rec.allowed_action}",
                f"  Rationale: {rec.rationale}",
                f"  Evidence: {', '.join(rec.evidence_sources)}",
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


class MetaEvolutionReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: MetaEvolutionReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
