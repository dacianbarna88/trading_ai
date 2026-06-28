"""
Confidence recalibration report model — Phase VI Sprint B4

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Recalibrates TAE confidence after accounting integrity fix — analysis only.
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

DEFAULT_RECALIBRATION_JSON_PATH = Path("tae_confidence_recalibration.json")
DEFAULT_RECALIBRATION_TXT_PATH = Path("tae_confidence_recalibration_summary.txt")
EVIDENCE_REGISTRY_CONSUMER_MODULE = (
    "research_core/evidence_engine/evidence_registry.py"
)
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_confidence_recalibration"


class ConfidenceStability(str, Enum):
    INCREASED = "INCREASED"
    UNCHANGED = "UNCHANGED"
    DECREASED = "DECREASED"


class ImplementationReadiness(str, Enum):
    NOT_READY = "NOT_READY"
    READY_FOR_SANDBOX_REVIEW = "READY_FOR_SANDBOX_REVIEW"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"


@dataclass
class PortfolioAccountingComparison:
    legacy_realized_pnl: float
    corrected_realized_pnl: float
    realized_pnl_delta: float
    legacy_win_rate: float
    corrected_win_rate: float
    legacy_high_severity_anomalies: int
    corrected_high_severity_anomalies: int
    conclusions_affected: bool
    notable_corrections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "legacy_realized_pnl": round(self.legacy_realized_pnl, 2),
            "corrected_realized_pnl": round(self.corrected_realized_pnl, 2),
            "realized_pnl_delta": round(self.realized_pnl_delta, 2),
            "legacy_win_rate": round(self.legacy_win_rate, 2),
            "corrected_win_rate": round(self.corrected_win_rate, 2),
            "legacy_high_severity_anomalies": self.legacy_high_severity_anomalies,
            "corrected_high_severity_anomalies": self.corrected_high_severity_anomalies,
            "conclusions_affected": self.conclusions_affected,
            "notable_corrections": list(self.notable_corrections),
        }


@dataclass
class CandidateRecalibration:
    candidate_id: str
    title: str
    old_confidence: float
    recalibrated_confidence: float
    old_evidence_score: float
    recalibrated_evidence_score: float
    old_readiness: str
    recalibrated_readiness: str
    accounting_impact: str
    confidence_delta: float
    evidence_score_delta: float
    confidence_stability: ConfidenceStability
    requires_review: bool
    rank_before: int
    rank_after: int
    validation_gaps_remain: bool
    recommendation_downgrade: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.confidence_stability, str):
            self.confidence_stability = ConfidenceStability(self.confidence_stability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title": self.title,
            "old_confidence": round(self.old_confidence, 2),
            "recalibrated_confidence": round(self.recalibrated_confidence, 2),
            "old_evidence_score": round(self.old_evidence_score, 2),
            "recalibrated_evidence_score": round(self.recalibrated_evidence_score, 2),
            "old_readiness": self.old_readiness,
            "recalibrated_readiness": self.recalibrated_readiness,
            "accounting_impact": self.accounting_impact,
            "confidence_delta": round(self.confidence_delta, 2),
            "evidence_score_delta": round(self.evidence_score_delta, 2),
            "confidence_stability": self.confidence_stability.value,
            "requires_review": self.requires_review,
            "rank_before": self.rank_before,
            "rank_after": self.rank_after,
            "validation_gaps_remain": self.validation_gaps_remain,
            "recommendation_downgrade": self.recommendation_downgrade,
        }


@dataclass
class EcosystemMetrics:
    average_old_confidence: float
    average_recalibrated_confidence: float
    average_confidence_delta: float
    ranking_changed: bool
    top_candidate_before: str
    top_candidate_after: str
    top_candidate_unchanged: bool
    conclusions_affected_by_accounting: bool
    recommendations_requiring_review: int
    patches_still_blocked: int
    evolution_plans_still_gated: int
    all_implementation_not_ready: bool
    implementation_readiness_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_old_confidence": round(self.average_old_confidence, 2),
            "average_recalibrated_confidence": round(self.average_recalibrated_confidence, 2),
            "average_confidence_delta": round(self.average_confidence_delta, 2),
            "ranking_changed": self.ranking_changed,
            "top_candidate_before": self.top_candidate_before,
            "top_candidate_after": self.top_candidate_after,
            "top_candidate_unchanged": self.top_candidate_unchanged,
            "conclusions_affected_by_accounting": self.conclusions_affected_by_accounting,
            "recommendations_requiring_review": self.recommendations_requiring_review,
            "patches_still_blocked": self.patches_still_blocked,
            "evolution_plans_still_gated": self.evolution_plans_still_gated,
            "all_implementation_not_ready": self.all_implementation_not_ready,
            "implementation_readiness_summary": self.implementation_readiness_summary,
        }


@dataclass
class ConfidenceRecalibrationReport:
    accounting_comparison: PortfolioAccountingComparison
    candidates: list[CandidateRecalibration]
    ecosystem: EcosystemMetrics
    next_recommended_research_action: str
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "accounting_comparison": self.accounting_comparison.to_dict(),
            "ecosystem": self.ecosystem.to_dict(),
            "next_recommended_research_action": self.next_recommended_research_action,
            "sources_loaded": dict(self.sources_loaded),
            "candidates": [c.to_dict() for c in self.candidates],
        }

    def format_summary(self) -> str:
        ac = self.accounting_comparison
        eco = self.ecosystem
        lines = [
            "===== RECALIBRARE ÎNCREDERE TAE — PHASE VI B4 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            "===== CE S-A SCHIMBAT DUPĂ CORECȚIA CONTABILĂ =====",
            f"PnL realizat legacy (concluzii vechi): {ac.legacy_realized_pnl:,.2f}",
            f"PnL realizat recalibrat (corect): {ac.corrected_realized_pnl:,.2f}",
            f"Delta PnL: {ac.realized_pnl_delta:+,.2f}",
            f"Win rate: {ac.legacy_win_rate:.1f}% → {ac.corrected_win_rate:.1f}%",
            f"Anomalii HIGH: {ac.legacy_high_severity_anomalies} → "
            f"{ac.corrected_high_severity_anomalies}",
        ]
        for note in ac.notable_corrections:
            lines.append(f"  • {note}")
        lines.extend([
            "",
            "===== CE NU S-A SCHIMBAT =====",
            "• Validarea cross-regime / cross-region din pipeline TAE (research-only)",
            "• Lipsa validării Europe/UK — blocaj implementare rămâne",
            "• Toate recomandările rămân NOT_IMPLEMENTED — fără execuție",
            "• Praguri strategie / entry filter — neatinse",
            "",
            "===== VALIDITATEA CONCLUZIILOR TAE =====",
        ])
        if ac.conclusions_affected:
            lines.append(
                "Concluziile din auditul de performanță strategică au fost afectate de "
                "bug-ul contabil (PnL SELL pe mark, nu pe preț execuție). "
                "Concluziile din cross-validation și experimente rămân valide."
            )
        else:
            lines.append("Concluziile TAE rămân valide — fără impact contabil detectat.")
        lines.extend([
            "",
            f"Ranking schimbat: {'DA' if eco.ranking_changed else 'NU'}",
            f"Top candidat înainte: {eco.top_candidate_before}",
            f"Top candidat după: {eco.top_candidate_after}",
            f"kn_d5_00002 rămâne top: {'DA' if eco.top_candidate_unchanged else 'NU'}",
            "",
            f"Implementare blocată (Europe/UK): {'DA' if eco.all_implementation_not_ready else 'NU'}",
            f"{eco.implementation_readiness_summary}",
            "",
            "===== RECALIBRARE PE CANDIDAT =====",
        ])
        for cand in sorted(self.candidates, key=lambda c: c.rank_after):
            lines.append(
                f"  {cand.candidate_id} | rank {cand.rank_before}→{cand.rank_after} | "
                f"conf {cand.old_confidence:.1f}→{cand.recalibrated_confidence:.1f} "
                f"({cand.confidence_stability.value}) | "
                f"readiness={cand.recalibrated_readiness}"
            )
            if cand.requires_review:
                lines.append(f"      requires_review: DA — {cand.recommendation_downgrade}")
        lines.extend([
            "",
            "Metrici ecosistem:",
            f"  Confidence mediu: {eco.average_old_confidence:.1f} → "
            f"{eco.average_recalibrated_confidence:.1f} "
            f"(delta {eco.average_confidence_delta:+.2f})",
            f"  Recomandări REQUIRE_REVIEW: {eco.recommendations_requiring_review}",
            f"  Patch-uri încă blocate: {eco.patches_still_blocked}",
            f"  Planuri evolution VALIDATION_GATE: {eco.evolution_plans_still_gated}",
            "",
            "===== URMĂTORUL PAS RECOMANDAT =====",
            self.next_recommended_research_action,
            "",
            "===== AVERTISMENT =====",
            "RESEARCH ONLY — NO EXECUTION",
            "NOT IMPLEMENTED — RECALIBRARE ANALITICĂ ONLY",
            "",
            "===== CONFIRMARE SIGURANȚĂ =====",
            "No live trading files were modified",
            "",
            "Recalibrare read-only — nu modifică portofoliu, strategie sau execuție.",
            "",
        ])
        return "\n".join(lines)


class RecalibrationStore:
    """JSON/TXT persistence — stdlib only."""

    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_RECALIBRATION_JSON_PATH
        self._txt_path = txt_path or DEFAULT_RECALIBRATION_TXT_PATH

    def persist(self, report: ConfidenceRecalibrationReport) -> Path:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: ConfidenceRecalibrationReport) -> Path:
        self._txt_path.write_text(report.format_summary() + "\n", encoding="utf-8")
        return self._txt_path
