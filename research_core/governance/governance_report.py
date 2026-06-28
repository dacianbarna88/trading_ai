"""
Governance report model — Phase V Sprint A5

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Executive daily intelligence report structure and persistence.
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

DEFAULT_JSON_PATH = Path("tae_daily_intelligence_report.json")
DEFAULT_TXT_PATH = Path("tae_daily_intelligence_report.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_daily_intelligence_report"


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    ATTENTION = "ATTENTION"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass
class DailyIntelligenceReport:
    report_date: str
    ecosystem_health: dict[str, Any]
    research_summary: dict[str, Any]
    learning_summary: dict[str, Any]
    validation_summary: dict[str, Any]
    strategy_evolution: dict[str, Any]
    research_priorities: list[dict[str, Any]]
    trading_status: dict[str, Any]
    roadmap_progress: dict[str, Any]
    critical_issues: list[str]
    executive_summary: list[str]
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    governance_modern_inputs: dict[str, Any] | None = None
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "report_date": self.report_date,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "ecosystem_health": self.ecosystem_health,
            "research_summary": self.research_summary,
            "learning_summary": self.learning_summary,
            "validation_summary": self.validation_summary,
            "strategy_evolution": self.strategy_evolution,
            "research_priorities": list(self.research_priorities),
            "trading_status": self.trading_status,
            "roadmap_progress": self.roadmap_progress,
            "critical_issues": list(self.critical_issues),
            "executive_summary": list(self.executive_summary),
            "sources_loaded": dict(self.sources_loaded),
            "governance_modern_inputs": dict(self.governance_modern_inputs)
            if isinstance(self.governance_modern_inputs, dict)
            else None,
        }

    def format_text(self) -> str:
        lines: list[str] = [
            "TAE DAILY INTELLIGENCE REPORT",
            f"Report date: {self.report_date}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Safety: {self.safety_mode}",
            "",
            "==================================================",
            "1. ECOSYSTEM HEALTH",
            "==================================================",
            "",
        ]

        components = self.ecosystem_health.get("components", [])
        for comp in components:
            if isinstance(comp, dict):
                lines.append(f"{comp.get('name', '')}: {comp.get('status', 'NOT_AVAILABLE')}")
                detail = comp.get("detail", "")
                if detail:
                    lines.append(f"  {detail}")
        overall = self.ecosystem_health.get("overall_status", "NOT_AVAILABLE")
        lines.extend(["", f"Overall status: {overall}", ""])

        lines.extend([
            "==================================================",
            "2. RESEARCH SUMMARY",
            "==================================================",
            "",
        ])
        for key, label in (
            ("hypotheses_total", "Hypotheses total"),
            ("hypotheses_tested", "Tested"),
            ("hypotheses_promoted", "Promoted (knowledge candidates)"),
            ("knowledge_candidates", "Knowledge candidates"),
            ("discoveries", "Discoveries"),
            ("discoveries_converted", "Converted discoveries"),
        ):
            lines.append(f"- {label}: {self.research_summary.get(key, 'NOT_AVAILABLE')}")

        lines.extend([
            "",
            "==================================================",
            "3. LEARNING SUMMARY",
            "==================================================",
            "",
        ])
        for key, label in (
            ("average_accuracy", "Average accuracy"),
            ("average_forward_return", "Average forward return"),
            ("learning_confidence", "Learning confidence"),
            ("best_organism", "Best organism"),
            ("strongest_hypothesis_family", "Strongest hypothesis family"),
        ):
            lines.append(f"- {label}: {self.learning_summary.get(key, 'NOT_AVAILABLE')}")

        lines.extend([
            "",
            "==================================================",
            "4. VALIDATION SUMMARY",
            "==================================================",
            "",
        ])
        for key, label in (
            ("cross_regime_consistency", "Cross-regime consistency"),
            ("cross_horizon_consistency", "Cross-horizon consistency"),
            ("cross_region_consistency", "Cross-region consistency"),
        ):
            lines.append(f"- {label}: {self.validation_summary.get(key, 'NOT_AVAILABLE')}")
        gaps = self.validation_summary.get("validation_gaps", [])
        lines.append("- Validation gaps:")
        if isinstance(gaps, list) and gaps:
            for gap in gaps:
                lines.append(f"  * {gap}")
        else:
            lines.append("  (none listed)")

        lines.extend([
            "",
            "==================================================",
            "5. STRATEGY EVOLUTION",
            "==================================================",
            "",
        ])
        for key, label in (
            ("recommendations", "Recommendations"),
            ("evolution_plans", "Evolution plans"),
            ("implementation_ready", "Implementation-ready"),
            ("blocked", "Blocked"),
            ("requiring_validation", "Requiring validation"),
        ):
            lines.append(f"- {label}: {self.strategy_evolution.get(key, 'NOT_AVAILABLE')}")

        lines.extend([
            "",
            "==================================================",
            "6. RESEARCH PRIORITIES",
            "==================================================",
            "",
        ])
        if self.research_priorities:
            for item in self.research_priorities:
                if isinstance(item, dict):
                    lines.append(
                        f"  #{item.get('rank', '?')} {item.get('opportunity_id', '')} "
                        f"(score={item.get('priority_score', '?')}) — {item.get('title', '')}"
                    )
        else:
            lines.append("  NOT_AVAILABLE")

        lines.extend([
            "",
            "==================================================",
            "7. TRADING STATUS",
            "==================================================",
            "",
        ])
        for key in (
            "bot_status",
            "dashboard_status",
            "market_regime",
            "process_health",
        ):
            val = self.trading_status.get(key, "NOT_AVAILABLE")
            lines.append(f"- {key.replace('_', ' ').title()}: {val}")

        lines.extend([
            "",
            "==================================================",
            "8. ROADMAP PROGRESS",
            "==================================================",
            "",
            f"Current maturity: {self.roadmap_progress.get('maturity_level', 'NOT_AVAILABLE')}",
            f"Completion %: {self.roadmap_progress.get('completion_pct', 'NOT_AVAILABLE')}",
            "",
            "Completed capabilities:",
        ])
        completed = self.roadmap_progress.get("completed_capabilities", [])
        if isinstance(completed, list) and completed:
            for cap in completed:
                lines.append(f"  - {cap}")
        else:
            lines.append("  NOT_AVAILABLE")
        lines.append("")
        lines.append("Remaining capabilities:")
        remaining = self.roadmap_progress.get("remaining_capabilities", [])
        if isinstance(remaining, list) and remaining:
            for cap in remaining:
                lines.append(f"  - {cap}")
        else:
            lines.append("  NOT_AVAILABLE")

        lines.extend([
            "",
            "==================================================",
            "9. CRITICAL ISSUES",
            "==================================================",
            "",
        ])
        if self.critical_issues:
            for issue in self.critical_issues:
                lines.append(f"- {issue}")
        else:
            lines.append("No critical issues detected.")

        lines.extend([
            "",
            "==================================================",
            "10. EXECUTIVE SUMMARY",
            "==================================================",
            "",
        ])
        for line in self.executive_summary:
            lines.append(line)
        lines.append("")
        if isinstance(self.governance_modern_inputs, dict):
            reg = self.governance_modern_inputs
            lines.extend([
                "==================================================",
                "11. GOVERNANCE MODERN INPUTS (Phase VIII/IX)",
                "==================================================",
                "",
                f"- Modern inputs registered: {reg.get('governance_modern_inputs_registered')}",
                f"- Modern input count: {reg.get('governance_modern_input_count')}",
                f"- Legacy input count: {reg.get('governance_legacy_input_count')}",
                f"- Legacy fallback only: {reg.get('governance_legacy_fallback_only')}",
                f"- Strategy evolution source: {reg.get('governance_strategy_evolution_source')}",
                "",
            ])
        lines.append("No live trading files modified by this report.")
        lines.append("")
        return "\n".join(lines)


class DailyIntelligenceStore:
    """Overwrite daily intelligence artifacts — stdlib json only."""

    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    @property
    def json_path(self) -> Path:
        return self._json_path

    @property
    def txt_path(self) -> Path:
        return self._txt_path

    def persist(self, report: DailyIntelligenceReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
