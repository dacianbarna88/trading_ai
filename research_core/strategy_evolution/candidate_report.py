"""
Candidate Strategy Registry report — Phase VIII B1

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

logger = logging.getLogger(__name__)


def _round_num(value: float, digits: int = 2) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


DEFAULT_JSON_PATH = Path("tae_candidate_strategy_registry.json")
DEFAULT_TXT_PATH = Path("tae_candidate_strategy_registry.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_candidate_strategy_registry"
SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class CandidateStatus(str, Enum):
    LIVE_BASELINE = "LIVE_BASELINE"
    PAPER_CANDIDATE = "PAPER_CANDIDATE"


class PromotionReadiness(str, Enum):
    NOT_READY = "NOT_READY"
    PAPER_TRACKING = "PAPER_TRACKING"
    PROMOTION_REVIEW_ELIGIBLE = "PROMOTION_REVIEW_ELIGIBLE"


class RegistryVerdict(str, Enum):
    CANDIDATE_STRATEGY_REGISTRY_READY = "CANDIDATE_STRATEGY_REGISTRY_READY"


@dataclass
class CandidateMetrics:
    trades: int
    closed_trades: int
    open_trades: int
    total_pnl: float
    avg_pnl: float
    median_pnl: float
    win_rate: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expectancy: float
    delta_vs_baseline_total_pnl: float
    delta_vs_baseline_expectancy: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "trades": self.trades,
            "closed_trades": self.closed_trades,
            "open_trades": self.open_trades,
            "total_pnl": _round_num(self.total_pnl, 2),
            "avg_pnl": _round_num(self.avg_pnl, 2),
            "median_pnl": _round_num(self.median_pnl, 2),
            "win_rate": _round_num(self.win_rate, 2),
            "gross_profit": _round_num(self.gross_profit, 2),
            "gross_loss": _round_num(self.gross_loss, 2),
            "profit_factor": _round_num(self.profit_factor, 4),
            "expectancy": _round_num(self.expectancy, 2),
            "delta_vs_baseline_total_pnl": _round_num(self.delta_vs_baseline_total_pnl, 2),
            "delta_vs_baseline_expectancy": _round_num(self.delta_vs_baseline_expectancy, 2),
        }


@dataclass
class StrategyCandidate:
    candidate_id: str
    title: str
    rule: str
    status: CandidateStatus
    source_evidence_id: str | None
    source_evidence_title: str | None
    metrics: CandidateMetrics
    promotion_readiness: PromotionReadiness
    simulation_lab_strategy_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title": self.title,
            "rule": self.rule,
            "status": self.status.value,
            "source_evidence_id": self.source_evidence_id,
            "source_evidence_title": self.source_evidence_title,
            "simulation_lab_strategy_id": self.simulation_lab_strategy_id,
            "promotion_readiness": self.promotion_readiness.value,
            "metrics": self.metrics.to_dict(),
        }


@dataclass
class CandidateRegistryReport:
    verdict: RegistryVerdict
    candidates: list[StrategyCandidate]
    baseline_candidate_id: str
    evidence_engine_verdict: str | None
    simulation_lab_verdict: str | None
    sources_loaded: dict[str, bool]
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
            "evidence_engine_verdict": self.evidence_engine_verdict,
            "simulation_lab_verdict": self.simulation_lab_verdict,
            "sources_loaded": dict(self.sources_loaded),
            "candidates": [c.to_dict() for c in self.candidates],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE CANDIDATE STRATEGY REGISTRY — FAZA VIII B1 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Baseline: {self.baseline_candidate_id}",
            f"Evidence Engine: {self.evidence_engine_verdict or 'N/A'}",
            f"Simulation Lab: {self.simulation_lab_verdict or 'N/A'}",
            "",
            "===== CANDIDAȚI STRATEGIE =====",
        ]
        for candidate in self.candidates:
            m = candidate.metrics
            lines.extend([
                f"--- {candidate.candidate_id} ---",
                f"  {candidate.title}",
                f"  Status: {candidate.status.value} | "
                f"Promotion: {candidate.promotion_readiness.value}",
                f"  Rule: {candidate.rule}",
            ])
            if candidate.source_evidence_id:
                lines.append(
                    f"  Evidence: {candidate.source_evidence_id}"
                    + (f" ({candidate.source_evidence_title})" if candidate.source_evidence_title else "")
                )
            lines.extend([
                f"  Trades: {m.trades} ({m.closed_trades} închise, {m.open_trades} deschise)",
                f"  Total PnL: ${m.total_pnl:,.2f} | delta vs baseline ${m.delta_vs_baseline_total_pnl:+,.2f}",
                f"  Win rate: {m.win_rate:.1f}% | PF {m.profit_factor:.4f} | "
                f"expectancy ${m.expectancy:,.2f} (delta {m.delta_vs_baseline_expectancy:+,.2f})",
                "",
            ])
        lines.extend([
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Fără instrucțiuni BUY/SELL — registru read-only.",
            "",
        ])
        return "\n".join(lines)


class CandidateRegistryReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: CandidateRegistryReport) -> Path:
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

    def persist_txt(self, report: CandidateRegistryReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
