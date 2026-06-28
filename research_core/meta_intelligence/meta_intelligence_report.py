"""
Meta Intelligence Report — Phase X Sprint X.2A

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

DEFAULT_JSON_PATH = Path("tae_meta_intelligence.json")
DEFAULT_TXT_PATH = Path("tae_meta_intelligence.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_meta_intelligence"


class MetaIntelligenceVerdict(str, Enum):
    META_INTELLIGENCE_READY = "META_INTELLIGENCE_READY"
    META_INTELLIGENCE_READY_WITH_WARNINGS = "META_INTELLIGENCE_READY_WITH_WARNINGS"
    META_INTELLIGENCE_INSUFFICIENT_DATA = "META_INTELLIGENCE_INSUFFICIENT_DATA"


@dataclass
class MetaIntelligenceReport:
    verdict: MetaIntelligenceVerdict
    sources_loaded: dict[str, bool]
    sources_loaded_count: int
    strategic_observations: dict[str, Any]
    canonical_inputs_read: list[str]
    warnings: list[str] = field(default_factory=list)
    protected_files_unchanged: bool = True
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "sources_loaded": dict(self.sources_loaded),
            "sources_loaded_count": self.sources_loaded_count,
            "strategic_observations": dict(self.strategic_observations),
            "canonical_inputs_read": list(self.canonical_inputs_read),
            "warnings": list(self.warnings),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        obs = self.strategic_observations
        lines = [
            "===== TAE META INTELLIGENCE — SPRINT X.2A =====",
            "",
            f"Safety banner: {self.safety_mode}",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            f"Canonical inputs loaded: {self.sources_loaded_count}/{len(self.sources_loaded)}",
            "",
            "===== STRATEGIC OBSERVATIONS =====",
            f"Overall ecosystem confidence: {obs.get('overall_ecosystem_confidence')}",
            f"Highest quality strategy: {obs.get('highest_quality_strategy')}",
            f"Weakest strategy: {obs.get('weakest_strategy')}",
            f"System maturity: {obs.get('system_maturity')}",
            "",
            "Promotion candidates:",
        ]
        for item in obs.get("promotion_candidates") or []:
            if isinstance(item, dict):
                lines.append(
                    f"  • {item.get('candidate_id')}: {item.get('reason')} "
                    f"(score={item.get('ranking_score', 'N/A')})"
                )
            else:
                lines.append(f"  • {item}")
        if not obs.get("promotion_candidates"):
            lines.append("  (none identified)")
        lines.append("")
        lines.append("Retirement candidates:")
        for item in obs.get("retirement_candidates") or []:
            if isinstance(item, dict):
                lines.append(
                    f"  • {item.get('candidate_id')}: {item.get('reason')} "
                    f"(score={item.get('ranking_score', item.get('profit_factor', 'N/A'))})"
                )
            else:
                lines.append(f"  • {item}")
        if not obs.get("retirement_candidates"):
            lines.append("  (none identified)")
        lines.extend([
            "",
            "===== SUMMARIES =====",
            f"Paper validation: {obs.get('paper_validation_summary')}",
            f"Runtime health: {obs.get('runtime_health_summary')}",
            f"Governance: {obs.get('governance_summary')}",
            "",
            "===== CANONICAL INPUTS =====",
        ])
        for name, loaded in self.sources_loaded.items():
            status = "loaded" if loaded else "missing"
            lines.append(f"  • {name}: {status}")
        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")
        lines.append("")
        return "\n".join(lines)


class MetaIntelligenceReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: MetaIntelligenceReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
