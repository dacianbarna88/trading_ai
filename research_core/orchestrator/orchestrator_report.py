"""
Ecosystem Orchestrator report — Phase VIII B8

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)


def _round_num(value: float, digits: int = 2) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


DEFAULT_JSON_PATH = Path("tae_ecosystem_orchestrator.json")
DEFAULT_TXT_PATH = Path("tae_ecosystem_orchestrator.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_ecosystem_orchestrator"


class OrchestratorVerdict(str, Enum):
    ECOSYSTEM_ORCHESTRATOR_READY = "ECOSYSTEM_ORCHESTRATOR_READY"
    ECOSYSTEM_ORCHESTRATOR_PARTIAL_FAILURE = "ECOSYSTEM_ORCHESTRATOR_PARTIAL_FAILURE"


@dataclass
class OrchestratorStepResult:
    step_number: int
    step_name: str
    subsystem: str
    verdict: str | None
    succeeded: bool
    output_json: str | None = None
    output_txt: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "subsystem": self.subsystem,
            "verdict": self.verdict,
            "succeeded": self.succeeded,
            "output_json": self.output_json,
            "output_txt": self.output_txt,
            "error": self.error,
        }


@dataclass
class PromotionGateSummary:
    review_candidate_id: str | None
    entries: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_candidate_id": self.review_candidate_id,
            "entries": list(self.entries),
        }


@dataclass
class PaperTrackingSummary:
    entries: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"entries": list(self.entries)}


@dataclass
class EcosystemOrchestratorReport:
    verdict: OrchestratorVerdict
    steps: list[OrchestratorStepResult]
    subsystem_verdicts: dict[str, str | None]
    top_ranked_strategy_id: str | None
    top_ranked_strategy_score: float | None
    promotion_review_candidate_id: str | None
    promotion_gate_summary: PromotionGateSummary
    paper_tracking_summary: PaperTrackingSummary
    missing_connections: list[str]
    do_not_rewrite: list[str]
    next_recommended_implementation: str
    final_ecosystem_recommendation: str
    protected_files_unchanged: bool
    strategy_state_source: str = "StrategyAdapter.load_strategy_state_for_orchestrator()"
    strategy_state_completeness: str | None = None
    strategy_adapter_id: str | None = None
    strategy_contract_validation: dict[str, Any] | None = None
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "steps": [step.to_dict() for step in self.steps],
            "subsystem_verdicts": dict(self.subsystem_verdicts),
            "top_ranked_strategy_id": self.top_ranked_strategy_id,
            "top_ranked_strategy_score": _round_num(self.top_ranked_strategy_score, 4)
            if self.top_ranked_strategy_score is not None
            else None,
            "promotion_review_candidate_id": self.promotion_review_candidate_id,
            "promotion_gate_summary": self.promotion_gate_summary.to_dict(),
            "paper_tracking_summary": self.paper_tracking_summary.to_dict(),
            "missing_connections": list(self.missing_connections),
            "do_not_rewrite": list(self.do_not_rewrite),
            "next_recommended_implementation": self.next_recommended_implementation,
            "final_ecosystem_recommendation": self.final_ecosystem_recommendation,
            "protected_files_unchanged": self.protected_files_unchanged,
            "strategy_state_source": self.strategy_state_source,
            "strategy_state_completeness": self.strategy_state_completeness,
            "strategy_adapter_id": self.strategy_adapter_id,
            "strategy_contract_validation": self.strategy_contract_validation,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE ECOSYSTEM ORCHESTRATOR — FAZA VIII B8 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== ORCHESTRATOR STEPS =====",
        ]
        for step in self.steps:
            status = "OK" if step.succeeded else "FAILED"
            lines.append(
                f"{step.step_number}. {step.step_name} [{status}] "
                f"verdict={step.verdict or 'N/A'}"
            )
            if step.error:
                lines.append(f"   Error: {step.error}")
        lines.extend(["", "===== SUBSYSTEM VERDICTS ====="])
        for name, verdict in self.subsystem_verdicts.items():
            lines.append(f"  {name}: {verdict or 'N/A'}")
        lines.extend([
            "",
            "===== STRATEGY ADAPTER PATH =====",
            f"Strategy state source: {self.strategy_state_source}",
            f"Strategy adapter: {self.strategy_adapter_id or 'N/A'}",
            f"Strategy state completeness: {self.strategy_state_completeness or 'N/A'}",
            "",
            "===== ECOSYSTEM INTELLIGENCE =====",
            f"Top ranked strategy: {self.top_ranked_strategy_id or 'N/A'}",
        ])
        if self.top_ranked_strategy_score is not None:
            lines.append(f"Top ranking score: {self.top_ranked_strategy_score:.4f}")
        lines.append(
            f"Promotion review candidate: {self.promotion_review_candidate_id or 'None'}"
        )
        lines.extend(["", "Paper tracking needs:"])
        for entry in self.paper_tracking_summary.entries:
            lines.append(
                f"  {entry.get('candidate_id')}: {entry.get('tracking_status')} | "
                f"trades={entry.get('current_trades')} need={entry.get('trades_needed')}"
            )
        lines.extend(["", "Missing connections:"])
        for conn in self.missing_connections:
            lines.append(f"  - {conn}")
        lines.extend([
            "",
            "===== DO NOT REWRITE =====",
        ])
        for path in self.do_not_rewrite:
            lines.append(f"  - {path}")
        lines.extend([
            "",
            f"Next recommended implementation: {self.next_recommended_implementation}",
            "",
            f"Final recommendation: {self.final_ecosystem_recommendation}",
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Orchestrator is read-only — no trade execution.",
            "",
        ])
        return "\n".join(lines)


class EcosystemOrchestratorReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: EcosystemOrchestratorReport) -> Path:
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

    def persist_txt(self, report: EcosystemOrchestratorReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
