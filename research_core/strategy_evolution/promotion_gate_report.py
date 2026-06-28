"""
Strategy Promotion Gate report — Phase VIII B4

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


DEFAULT_JSON_PATH = Path("tae_strategy_promotion_gate.json")
DEFAULT_TXT_PATH = Path("tae_strategy_promotion_gate.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_strategy_promotion_gate"

PROMOTION_SCORE_THRESHOLD = 0.70
PROMOTION_MIN_TRADES = 20


class PromotionGateDecision(str, Enum):
    BASELINE_REFERENCE = "BASELINE_REFERENCE"
    BLOCKED_INSUFFICIENT_SAMPLE = "BLOCKED_INSUFFICIENT_SAMPLE"
    BLOCKED_MIN_SAMPLE_NOT_MET = "BLOCKED_MIN_SAMPLE_NOT_MET"
    BLOCKED_SCORE_TOO_LOW = "BLOCKED_SCORE_TOO_LOW"
    BLOCKED_BELOW_BASELINE = "BLOCKED_BELOW_BASELINE"
    PROMOTION_REVIEW_ELIGIBLE = "PROMOTION_REVIEW_ELIGIBLE"


class PromotionGateVerdict(str, Enum):
    STRATEGY_PROMOTION_GATE_READY = "STRATEGY_PROMOTION_GATE_READY"


@dataclass
class PromotionGateEntry:
    candidate_id: str
    decision: PromotionGateDecision
    trades: int
    ranking_score: float
    blockers: list[str]
    required_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision.value,
            "trades": self.trades,
            "ranking_score": _round_num(self.ranking_score, 4),
            "blockers": list(self.blockers),
            "required_next_step": self.required_next_step,
        }


@dataclass
class PromotionGateReport:
    verdict: PromotionGateVerdict
    entries: list[PromotionGateEntry]
    baseline_candidate_id: str
    review_candidate_id: str | None
    ranking_verdict: str | None
    validation_verdict: str | None
    registry_verdict: str | None
    sources_loaded: dict[str, bool]
    regional_validation_registration: dict[str, Any] | None = None
    pipeline_reference: dict[str, Any] | None = None
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "baseline_candidate_id": self.baseline_candidate_id,
            "review_candidate_id": self.review_candidate_id,
            "ranking_verdict": self.ranking_verdict,
            "validation_verdict": self.validation_verdict,
            "registry_verdict": self.registry_verdict,
            "sources_loaded": dict(self.sources_loaded),
            "regional_validation_registration": dict(self.regional_validation_registration)
            if self.regional_validation_registration
            else None,
            "pipeline_reference": self.pipeline_reference,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE STRATEGY PROMOTION GATE — FAZA VIII B4 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Baseline: {self.baseline_candidate_id}",
            f"Review candidate: {self.review_candidate_id or 'None'}",
            f"Ranking: {self.ranking_verdict or 'N/A'}",
            f"Validation: {self.validation_verdict or 'N/A'}",
            f"Registry: {self.registry_verdict or 'N/A'}",
            "",
        ]
        if self.regional_validation_registration:
            reg = self.regional_validation_registration
            lines.extend([
                "===== REGIONAL VALIDATION REGISTRATION =====",
                f"  regional_validation_registered: {reg.get('regional_validation_registered')}",
                f"  regional_validation_status: {reg.get('regional_validation_status')}",
                f"  regional_validation_source: {reg.get('regional_validation_source')}",
                f"  regional_validation_last_refresh: {reg.get('regional_validation_last_refresh')}",
                "",
            ])
        lines.extend([
            "===== PROMOTION GATE =====",
        ])
        for entry in self.entries:
            blockers = ", ".join(entry.blockers) if entry.blockers else "none"
            lines.extend([
                f"--- {entry.candidate_id} ---",
                f"  Decision: {entry.decision.value}",
                f"  Trades: {entry.trades} | Ranking score: {entry.ranking_score:.4f}",
                f"  Blockers: {blockers}",
                f"  Next step: {entry.required_next_step}",
                "",
            ])
        lines.extend([
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Promotion gate is review-only — no strategy implementation.",
            "",
        ])
        return "\n".join(lines)


class PromotionGateReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: PromotionGateReport) -> Path:
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

    def persist_txt(self, report: PromotionGateReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
