"""
Continuous Strategy Ranking Engine — Phase VIII B3

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Ranks candidate strategies from parallel paper validation results.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.continuous_ranking_report import (
    INSUFFICIENT_SAMPLE_MIN_TRADES,
    PROMOTION_MIN_TRADES,
    PROMOTION_SCORE_THRESHOLD,
    SAMPLE_SIZE_CAP_TRADES,
    STRONG_CANDIDATE_MIN_TRADES,
    STRONG_CANDIDATE_SCORE_THRESHOLD,
    WEIGHT_EXPECTANCY_DELTA,
    WEIGHT_PROFIT_FACTOR,
    WEIGHT_SAMPLE_SIZE,
    WEIGHT_TOTAL_PNL_DELTA,
    WEIGHT_WIN_RATE,
    ContinuousStrategyRankingReport,
    RankingDecision,
    RankingVerdict,
    StrategyRankingEntry,
)

logger = logging.getLogger(__name__)

VALIDATION_PATH = Path("tae_parallel_paper_validation.json")
REGISTRY_PATH = Path("tae_candidate_strategy_registry.json")


@dataclass
class _ValidationRow:
    candidate_id: str
    validation_status: str
    trades: int
    total_pnl: float
    delta_vs_baseline_total_pnl: float
    profit_factor: float
    expectancy: float
    delta_vs_baseline_expectancy: float
    win_rate: float


class ContinuousStrategyRankingEngine:
    def __init__(
        self,
        validation_path: Path | str = VALIDATION_PATH,
        registry_path: Path | str = REGISTRY_PATH,
    ) -> None:
        self._validation_path = Path(validation_path)
        self._registry_path = Path(registry_path)

    def rank(self) -> ContinuousStrategyRankingReport:
        validation_payload = self._load_json(self._validation_path)
        registry_payload = self._load_json(self._registry_path)

        rows = self._parse_validations(validation_payload)
        baseline_id = str(
            (validation_payload or {}).get("baseline_candidate_id") or "LIVE_BASELINE"
        )

        scored = [self._score_row(row, rows) for row in rows]
        ranked = self._assign_ranks(scored, baseline_id)

        return ContinuousStrategyRankingReport(
            verdict=RankingVerdict.CONTINUOUS_STRATEGY_RANKING_READY,
            rankings=ranked,
            baseline_candidate_id=baseline_id,
            validation_verdict=str(validation_payload.get("verdict"))
            if validation_payload
            else None,
            registry_verdict=str(registry_payload.get("verdict"))
            if registry_payload
            else None,
            sources_loaded={
                self._validation_path.name: validation_payload is not None,
                self._registry_path.name: registry_payload is not None,
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

    def _parse_validations(
        self,
        validation_payload: dict[str, Any] | None,
    ) -> list[_ValidationRow]:
        if not validation_payload:
            return []
        validations = validation_payload.get("validations", [])
        if not isinstance(validations, list):
            return []

        rows: list[_ValidationRow] = []
        for item in validations:
            if not isinstance(item, dict) or not item.get("candidate_id"):
                continue
            rows.append(
                _ValidationRow(
                    candidate_id=str(item["candidate_id"]),
                    validation_status=str(item.get("validation_status", "")),
                    trades=int(item.get("trades") or 0),
                    total_pnl=float(item.get("total_pnl") or 0.0),
                    delta_vs_baseline_total_pnl=float(
                        item.get("delta_vs_baseline_total_pnl") or 0.0
                    ),
                    profit_factor=float(item.get("profit_factor") or 0.0),
                    expectancy=float(item.get("expectancy") or 0.0),
                    delta_vs_baseline_expectancy=float(
                        item.get("delta_vs_baseline_expectancy") or 0.0
                    ),
                    win_rate=float(item.get("win_rate") or 0.0),
                )
            )
        return rows

    def _score_row(
        self,
        row: _ValidationRow,
        all_rows: list[_ValidationRow],
    ) -> StrategyRankingEntry:
        pnl_deltas = [r.delta_vs_baseline_total_pnl for r in all_rows]
        profit_factors = [r.profit_factor for r in all_rows]
        expectancy_deltas = [r.delta_vs_baseline_expectancy for r in all_rows]

        norm_pnl_delta = _min_max_normalize(row.delta_vs_baseline_total_pnl, pnl_deltas)
        norm_pf = _min_max_normalize(row.profit_factor, profit_factors)
        norm_exp_delta = _min_max_normalize(
            row.delta_vs_baseline_expectancy,
            expectancy_deltas,
        )
        norm_win_rate = max(0.0, min(1.0, row.win_rate / 100.0))
        sample_size_factor = min(1.0, row.trades / SAMPLE_SIZE_CAP_TRADES)

        ranking_score = (
            WEIGHT_TOTAL_PNL_DELTA * norm_pnl_delta
            + WEIGHT_PROFIT_FACTOR * norm_pf
            + WEIGHT_EXPECTANCY_DELTA * norm_exp_delta
            + WEIGHT_WIN_RATE * norm_win_rate
            + WEIGHT_SAMPLE_SIZE * sample_size_factor
        )

        return StrategyRankingEntry(
            candidate_id=row.candidate_id,
            validation_status=row.validation_status,
            trades=row.trades,
            total_pnl=row.total_pnl,
            delta_vs_baseline_total_pnl=row.delta_vs_baseline_total_pnl,
            profit_factor=row.profit_factor,
            expectancy=row.expectancy,
            win_rate=row.win_rate,
            sample_size_factor=round(sample_size_factor, 4),
            ranking_score=round(ranking_score, 4),
            rank=0,
            decision=RankingDecision.KEEP_TRACKING,
        )

    def _assign_ranks(
        self,
        entries: list[StrategyRankingEntry],
        baseline_id: str,
    ) -> list[StrategyRankingEntry]:
        ordered = sorted(
            entries,
            key=lambda e: (-e.ranking_score, e.candidate_id),
        )
        ranked: list[StrategyRankingEntry] = []
        for index, entry in enumerate(ordered, start=1):
            ranked.append(
                StrategyRankingEntry(
                    candidate_id=entry.candidate_id,
                    validation_status=entry.validation_status,
                    trades=entry.trades,
                    total_pnl=entry.total_pnl,
                    delta_vs_baseline_total_pnl=entry.delta_vs_baseline_total_pnl,
                    profit_factor=entry.profit_factor,
                    expectancy=entry.expectancy,
                    win_rate=entry.win_rate,
                    sample_size_factor=entry.sample_size_factor,
                    ranking_score=entry.ranking_score,
                    rank=index,
                    decision=self._decision(entry, baseline_id),
                )
            )
        return ranked

    @staticmethod
    def _decision(entry: StrategyRankingEntry, baseline_id: str) -> RankingDecision:
        if entry.candidate_id == baseline_id:
            return RankingDecision.BASELINE_REFERENCE
        if entry.trades < INSUFFICIENT_SAMPLE_MIN_TRADES:
            return RankingDecision.INSUFFICIENT_SAMPLE
        if (
            entry.ranking_score >= PROMOTION_SCORE_THRESHOLD
            and entry.trades >= PROMOTION_MIN_TRADES
        ):
            return RankingDecision.PROMOTION_REVIEW_ELIGIBLE
        if (
            entry.ranking_score >= STRONG_CANDIDATE_SCORE_THRESHOLD
            and entry.trades >= STRONG_CANDIDATE_MIN_TRADES
        ):
            return RankingDecision.STRONG_PAPER_CANDIDATE
        return RankingDecision.KEEP_TRACKING


def _min_max_normalize(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return 1.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))
