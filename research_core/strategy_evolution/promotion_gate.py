"""
Strategy Promotion Gate — Phase VIII B4 / IX.2C pipeline step 4

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Review-only gate: decides whether paper candidates are eligible for implementation review.
No execution or live strategy changes. Not a direct entry point.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.pipeline_integration import pipeline_reference
from research_core.strategy_evolution.regional_validation_integration import (
    REGIONAL_VALIDATION_REPORT_PATH,
)
from research_core.strategy_evolution.promotion_gate_report import (
    PROMOTION_MIN_TRADES,
    PROMOTION_SCORE_THRESHOLD,
    PromotionGateDecision,
    PromotionGateEntry,
    PromotionGateReport,
    PromotionGateVerdict,
)

logger = logging.getLogger(__name__)

PIPELINE_ROLE = "PIPELINE_STEP_PROMOTION_REVIEW_ONLY"

RANKING_PATH = Path("tae_continuous_strategy_ranking.json")
VALIDATION_PATH = Path("tae_parallel_paper_validation.json")
REGISTRY_PATH = Path("tae_candidate_strategy_registry.json")

BLOCKER_INSUFFICIENT_SAMPLE = "VALIDATION_STATUS_INSUFFICIENT_SAMPLE"
BLOCKER_MIN_SAMPLE = "TRADES_BELOW_20"
BLOCKER_SCORE = "RANKING_SCORE_BELOW_0.70"
BLOCKER_PNL = "DOES_NOT_BEAT_BASELINE_TOTAL_PNL"
BLOCKER_PF = "DOES_NOT_BEAT_BASELINE_PROFIT_FACTOR"
BLOCKER_EXP = "DOES_NOT_BEAT_BASELINE_EXPECTANCY"


@dataclass
class _CandidateContext:
    candidate_id: str
    validation_status: str
    trades: int
    ranking_score: float
    total_pnl: float
    profit_factor: float
    expectancy: float
    beats_baseline_total_pnl: bool
    beats_baseline_profit_factor: bool
    beats_baseline_expectancy: bool


class StrategyPromotionGate:
    def __init__(
        self,
        ranking_path: Path | str = RANKING_PATH,
        validation_path: Path | str = VALIDATION_PATH,
        registry_path: Path | str = REGISTRY_PATH,
    ) -> None:
        self._ranking_path = Path(ranking_path)
        self._validation_path = Path(validation_path)
        self._registry_path = Path(registry_path)

    def evaluate(self) -> PromotionGateReport:
        ranking_payload = self._load_json(self._ranking_path)
        validation_payload = self._load_json(self._validation_path)
        registry_payload = self._load_json(self._registry_path)
        regional_payload = self._load_json(REGIONAL_VALIDATION_REPORT_PATH)

        baseline_id = str(
            (ranking_payload or {}).get("baseline_candidate_id")
            or (validation_payload or {}).get("baseline_candidate_id")
            or "LIVE_BASELINE"
        )

        contexts = self._build_contexts(ranking_payload, validation_payload)
        entries = [self._evaluate_candidate(ctx, baseline_id) for ctx in contexts]

        review_candidate_id = next(
            (
                entry.candidate_id
                for entry in entries
                if entry.decision == PromotionGateDecision.PROMOTION_REVIEW_ELIGIBLE
            ),
            None,
        )

        from research_core.strategy_evolution.regional_validation_integration import (
            build_regional_validation_registration,
        )

        regional_validation_registration = build_regional_validation_registration(
            Path("."),
            regional_payload,
        )

        sources_loaded = {
            self._ranking_path.name: ranking_payload is not None,
            self._validation_path.name: validation_payload is not None,
            self._registry_path.name: registry_payload is not None,
            REGIONAL_VALIDATION_REPORT_PATH.name: regional_payload is not None,
        }

        return PromotionGateReport(
            verdict=PromotionGateVerdict.STRATEGY_PROMOTION_GATE_READY,
            entries=entries,
            baseline_candidate_id=baseline_id,
            review_candidate_id=review_candidate_id,
            ranking_verdict=str(ranking_payload.get("verdict")) if ranking_payload else None,
            validation_verdict=str(validation_payload.get("verdict"))
            if validation_payload
            else None,
            registry_verdict=str(registry_payload.get("verdict")) if registry_payload else None,
            sources_loaded=sources_loaded,
            regional_validation_registration=regional_validation_registration,
            pipeline_reference={
                **pipeline_reference(),
                "pipeline_role": PIPELINE_ROLE,
                "pipeline_step": 4,
                "review_only": True,
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

    def _build_contexts(
        self,
        ranking_payload: dict[str, Any] | None,
        validation_payload: dict[str, Any] | None,
    ) -> list[_CandidateContext]:
        rankings = (ranking_payload or {}).get("rankings", [])
        validations = (validation_payload or {}).get("validations", [])
        if not isinstance(rankings, list):
            rankings = []

        validation_by_id: dict[str, dict[str, Any]] = {}
        if isinstance(validations, list):
            for item in validations:
                if isinstance(item, dict) and item.get("candidate_id"):
                    validation_by_id[str(item["candidate_id"])] = item

        contexts: list[_CandidateContext] = []
        for ranking in rankings:
            if not isinstance(ranking, dict) or not ranking.get("candidate_id"):
                continue
            candidate_id = str(ranking["candidate_id"])
            validation = validation_by_id.get(candidate_id, {})
            contexts.append(
                _CandidateContext(
                    candidate_id=candidate_id,
                    validation_status=str(
                        ranking.get("validation_status")
                        or validation.get("validation_status")
                        or ""
                    ),
                    trades=int(ranking.get("trades") or validation.get("trades") or 0),
                    ranking_score=float(ranking.get("ranking_score") or 0.0),
                    total_pnl=float(ranking.get("total_pnl") or validation.get("total_pnl") or 0.0),
                    profit_factor=float(
                        ranking.get("profit_factor") or validation.get("profit_factor") or 0.0
                    ),
                    expectancy=float(
                        ranking.get("expectancy") or validation.get("expectancy") or 0.0
                    ),
                    beats_baseline_total_pnl=bool(
                        validation.get("beats_baseline_total_pnl", False)
                    ),
                    beats_baseline_profit_factor=bool(
                        validation.get("beats_baseline_profit_factor", False)
                    ),
                    beats_baseline_expectancy=bool(
                        validation.get("beats_baseline_expectancy", False)
                    ),
                )
            )
        return contexts

    def _evaluate_candidate(
        self,
        ctx: _CandidateContext,
        baseline_id: str,
    ) -> PromotionGateEntry:
        if ctx.candidate_id == baseline_id:
            return PromotionGateEntry(
                candidate_id=ctx.candidate_id,
                decision=PromotionGateDecision.BASELINE_REFERENCE,
                trades=ctx.trades,
                ranking_score=ctx.ranking_score,
                blockers=[],
                required_next_step="Maintain as live reference baseline — no promotion path.",
            )

        blockers = self._collect_blockers(ctx)
        decision = self._decision_from_blockers(blockers)
        return PromotionGateEntry(
            candidate_id=ctx.candidate_id,
            decision=decision,
            trades=ctx.trades,
            ranking_score=ctx.ranking_score,
            blockers=blockers,
            required_next_step=self._required_next_step(decision, ctx),
        )

    @staticmethod
    def _collect_blockers(ctx: _CandidateContext) -> list[str]:
        blockers: list[str] = []
        if ctx.validation_status == "INSUFFICIENT_SAMPLE":
            blockers.append(BLOCKER_INSUFFICIENT_SAMPLE)
        if ctx.trades < PROMOTION_MIN_TRADES:
            blockers.append(BLOCKER_MIN_SAMPLE)
        if ctx.ranking_score < PROMOTION_SCORE_THRESHOLD:
            blockers.append(BLOCKER_SCORE)
        if not ctx.beats_baseline_total_pnl:
            blockers.append(BLOCKER_PNL)
        if not ctx.beats_baseline_profit_factor:
            blockers.append(BLOCKER_PF)
        if not ctx.beats_baseline_expectancy:
            blockers.append(BLOCKER_EXP)
        return blockers

    @staticmethod
    def _decision_from_blockers(blockers: list[str]) -> PromotionGateDecision:
        if not blockers:
            return PromotionGateDecision.PROMOTION_REVIEW_ELIGIBLE
        if BLOCKER_INSUFFICIENT_SAMPLE in blockers:
            return PromotionGateDecision.BLOCKED_INSUFFICIENT_SAMPLE
        if BLOCKER_MIN_SAMPLE in blockers:
            return PromotionGateDecision.BLOCKED_MIN_SAMPLE_NOT_MET
        if BLOCKER_SCORE in blockers:
            return PromotionGateDecision.BLOCKED_SCORE_TOO_LOW
        return PromotionGateDecision.BLOCKED_BELOW_BASELINE

    @staticmethod
    def _required_next_step(
        decision: PromotionGateDecision,
        ctx: _CandidateContext,
    ) -> str:
        if decision == PromotionGateDecision.BASELINE_REFERENCE:
            return "Maintain as live reference baseline — no promotion path."
        if decision == PromotionGateDecision.BLOCKED_INSUFFICIENT_SAMPLE:
            return "Continue paper tracking until validation sample is sufficient."
        if decision == PromotionGateDecision.BLOCKED_MIN_SAMPLE_NOT_MET:
            remaining = max(0, PROMOTION_MIN_TRADES - ctx.trades)
            return (
                f"Continue paper tracking — need {remaining} more trade(s) "
                f"to reach minimum sample of {PROMOTION_MIN_TRADES}."
            )
        if decision == PromotionGateDecision.BLOCKED_SCORE_TOO_LOW:
            return (
                f"Improve ranking score to >= {PROMOTION_SCORE_THRESHOLD:.2f} "
                f"(current {ctx.ranking_score:.4f})."
            )
        if decision == PromotionGateDecision.BLOCKED_BELOW_BASELINE:
            return "Must beat baseline on total PnL, profit factor, and expectancy."
        return (
            "Eligible for implementation review only — "
            "no auto-implementation or live strategy change."
        )
