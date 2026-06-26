"""
Paper Tracking Log — Phase VIII B5

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Tracks how many additional trades each paper candidate needs
before promotion review eligibility.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_registry import CandidateStrategyRegistry
from research_core.strategy_evolution.paper_tracking_report import (
    MIN_REQUIRED_TRADES,
    PaperTrackingEntry,
    PaperTrackingLogReport,
    PaperTrackingVerdict,
    TrackingStatus,
)
from research_core.strategy_evolution.promotion_gate_report import PromotionGateDecision

logger = logging.getLogger(__name__)

PROMOTION_GATE_PATH = Path("tae_strategy_promotion_gate.json")
RANKING_PATH = Path("tae_continuous_strategy_ranking.json")
VALIDATION_PATH = Path("tae_parallel_paper_validation.json")
PORTFOLIO_PATH = Path("portfolio.csv")


@dataclass
class _CandidateSnapshot:
    candidate_id: str
    current_trades: int
    closed_trades: int
    open_trades: int
    total_pnl: float
    profit_factor: float
    expectancy: float


class PaperTrackingLog:
    def __init__(
        self,
        promotion_gate_path: Path | str = PROMOTION_GATE_PATH,
        ranking_path: Path | str = RANKING_PATH,
        validation_path: Path | str = VALIDATION_PATH,
        portfolio_csv: Path | str = PORTFOLIO_PATH,
    ) -> None:
        self._promotion_gate_path = Path(promotion_gate_path)
        self._ranking_path = Path(ranking_path)
        self._validation_path = Path(validation_path)
        self._portfolio_csv = Path(portfolio_csv)

    def build(self) -> PaperTrackingLogReport:
        gate_payload = self._load_json(self._promotion_gate_path)
        ranking_payload = self._load_json(self._ranking_path)
        validation_payload = self._load_json(self._validation_path)

        baseline_id = str(
            (gate_payload or {}).get("baseline_candidate_id")
            or (ranking_payload or {}).get("baseline_candidate_id")
            or "LIVE_BASELINE"
        )

        registry_report = CandidateStrategyRegistry(
            portfolio_csv=self._portfolio_csv,
        ).build()
        snapshots = {
            c.candidate_id: _CandidateSnapshot(
                candidate_id=c.candidate_id,
                current_trades=c.metrics.trades,
                closed_trades=c.metrics.closed_trades,
                open_trades=c.metrics.open_trades,
                total_pnl=c.metrics.total_pnl,
                profit_factor=c.metrics.profit_factor,
                expectancy=c.metrics.expectancy,
            )
            for c in registry_report.candidates
        }

        gate_by_id = self._index_gate_entries(gate_payload)
        ranking_by_id = self._index_rankings(ranking_payload)
        validation_by_id = self._index_validations(validation_payload)

        candidate_ids = list(gate_by_id.keys()) or list(snapshots.keys())
        entries: list[PaperTrackingEntry] = []
        for candidate_id in candidate_ids:
            snapshot = snapshots.get(candidate_id)
            gate_entry = gate_by_id.get(candidate_id, {})
            ranking_entry = ranking_by_id.get(candidate_id, {})
            validation_entry = validation_by_id.get(candidate_id, {})

            current_trades = (
                snapshot.current_trades
                if snapshot
                else int(gate_entry.get("trades") or validation_entry.get("trades") or 0)
            )
            closed_trades = (
                snapshot.closed_trades
                if snapshot
                else int(validation_entry.get("closed_trades") or 0)
            )
            open_trades = (
                snapshot.open_trades
                if snapshot
                else int(validation_entry.get("open_trades") or 0)
            )
            trades_needed = max(0, MIN_REQUIRED_TRADES - current_trades)

            validation_status = str(
                validation_entry.get("validation_status")
                or ranking_entry.get("validation_status")
                or ""
            )
            promotion_gate_decision = str(gate_entry.get("decision") or "")
            ranking_score = float(
                ranking_entry.get("ranking_score") or gate_entry.get("ranking_score") or 0.0
            )
            current_total_pnl = float(
                snapshot.total_pnl
                if snapshot
                else validation_entry.get("total_pnl") or ranking_entry.get("total_pnl") or 0.0
            )
            profit_factor = float(
                snapshot.profit_factor
                if snapshot
                else validation_entry.get("profit_factor") or ranking_entry.get("profit_factor") or 0.0
            )
            expectancy = float(
                snapshot.expectancy
                if snapshot
                else validation_entry.get("expectancy") or ranking_entry.get("expectancy") or 0.0
            )

            sample_insufficient = (
                validation_status == "INSUFFICIENT_SAMPLE"
                or promotion_gate_decision
                == PromotionGateDecision.BLOCKED_INSUFFICIENT_SAMPLE.value
            )
            tracking_status = self._tracking_status(
                candidate_id=candidate_id,
                baseline_id=baseline_id,
                promotion_gate_decision=promotion_gate_decision,
                sample_insufficient=sample_insufficient,
            )
            tracking_note = self._tracking_note(
                tracking_status=tracking_status,
                trades_needed=trades_needed,
                sample_insufficient=sample_insufficient,
                gate_next_step=str(gate_entry.get("required_next_step") or ""),
            )

            entries.append(
                PaperTrackingEntry(
                    candidate_id=candidate_id,
                    current_trades=current_trades,
                    closed_trades=closed_trades,
                    open_trades=open_trades,
                    min_required_trades=MIN_REQUIRED_TRADES,
                    trades_needed=trades_needed,
                    validation_status=validation_status,
                    promotion_gate_decision=promotion_gate_decision,
                    ranking_score=ranking_score,
                    current_total_pnl=current_total_pnl,
                    profit_factor=profit_factor,
                    expectancy=expectancy,
                    tracking_status=tracking_status,
                    sample_insufficient=sample_insufficient,
                    tracking_note=tracking_note,
                )
            )

        return PaperTrackingLogReport(
            verdict=PaperTrackingVerdict.PAPER_TRACKING_LOG_READY,
            entries=entries,
            baseline_candidate_id=baseline_id,
            promotion_gate_verdict=str(gate_payload.get("verdict")) if gate_payload else None,
            ranking_verdict=str(ranking_payload.get("verdict")) if ranking_payload else None,
            validation_verdict=str(validation_payload.get("verdict"))
            if validation_payload
            else None,
            sources_loaded={
                self._promotion_gate_path.name: gate_payload is not None,
                self._ranking_path.name: ranking_payload is not None,
                self._validation_path.name: validation_payload is not None,
                self._portfolio_csv.name: self._portfolio_csv.is_file(),
            },
        )

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            logger.warning("Input not found: %s", path)
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _index_gate_entries(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        entries = (payload or {}).get("entries", [])
        if not isinstance(entries, list):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for item in entries:
            if isinstance(item, dict) and item.get("candidate_id"):
                out[str(item["candidate_id"])] = item
        return out

    @staticmethod
    def _index_rankings(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        rankings = (payload or {}).get("rankings", [])
        if not isinstance(rankings, list):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for item in rankings:
            if isinstance(item, dict) and item.get("candidate_id"):
                out[str(item["candidate_id"])] = item
        return out

    @staticmethod
    def _index_validations(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        validations = (payload or {}).get("validations", [])
        if not isinstance(validations, list):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for item in validations:
            if isinstance(item, dict) and item.get("candidate_id"):
                out[str(item["candidate_id"])] = item
        return out

    @staticmethod
    def _tracking_status(
        candidate_id: str,
        baseline_id: str,
        promotion_gate_decision: str,
        sample_insufficient: bool,
    ) -> TrackingStatus:
        if candidate_id == baseline_id:
            return TrackingStatus.BASELINE_REFERENCE
        if promotion_gate_decision == PromotionGateDecision.PROMOTION_REVIEW_ELIGIBLE.value:
            return TrackingStatus.READY_FOR_REVIEW
        if sample_insufficient:
            return TrackingStatus.BLOCKED
        if promotion_gate_decision == PromotionGateDecision.BLOCKED_MIN_SAMPLE_NOT_MET.value:
            return TrackingStatus.TRACKING_ACTIVE
        return TrackingStatus.BLOCKED

    @staticmethod
    def _tracking_note(
        tracking_status: TrackingStatus,
        trades_needed: int,
        sample_insufficient: bool,
        gate_next_step: str,
    ) -> str:
        if tracking_status == TrackingStatus.BASELINE_REFERENCE:
            return "Live baseline reference — not a paper promotion candidate."
        if tracking_status == TrackingStatus.READY_FOR_REVIEW:
            return "Sample and gate criteria met — eligible for promotion review only."
        if sample_insufficient:
            return (
                "Sample insufficient for promotion review. "
                + (gate_next_step or "Continue paper tracking.")
            )
        if tracking_status == TrackingStatus.TRACKING_ACTIVE:
            return (
                f"Actively tracking toward {MIN_REQUIRED_TRADES} trades — "
                f"need {trades_needed} more qualifying trade(s)."
            )
        return gate_next_step or "Blocked from promotion review."
