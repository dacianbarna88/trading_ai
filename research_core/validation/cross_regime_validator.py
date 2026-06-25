"""
Cross-regime & multi-horizon validator — Phase IV Sprint D6

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Measures knowledge candidate robustness across regimes, horizons, and regions.
Does not estimate missing dimensions — reports NOT_AVAILABLE.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.hypothesis.hypothesis_registry import HypothesisRegistry
from research_core.hypothesis.experiment_runner import (
    DEFAULT_ENSEMBLE_PATH,
    FORWARD_RETURN_COL,
    ResearchDataLoader,
    _row_matches_conditions,
)
from research_core.hypothesis.knowledge_candidate import (
    KnowledgeCandidate,
    KnowledgeCandidateRegistry,
)
from research_core.validation.validation_report import (
    CandidateValidationResult,
    CrossValidationReport,
    DimensionSlice,
    NOT_AVAILABLE,
)

logger = logging.getLogger(__name__)

MIN_SLICE_SAMPLE = 5
REGIMES = ("BULL", "BEAR", "NEUTRAL")
HORIZONS = ("2Y", "5Y", "10Y", "20Y")
HORIZON_YEARS = {"2Y": 2, "5Y": 5, "10Y": 10, "20Y": 20}
REGIONS = ("US", "Europe", "UK")

REGIONAL_STRENGTH_PATH = Path("regional_strength.csv")
MULTI_HORIZON_PATH = Path("multi_horizon_backtest.csv")
HORIZON_VALIDATION_PATH = Path("horizon_validation.csv")


class CrossRegimeValidator:
    """
    Validates knowledge candidates across regime, horizon, and region dimensions.
    Sprint D6 — research-only robustness measurement, not execution.
    """

    def __init__(
        self,
        candidate_registry: KnowledgeCandidateRegistry | None = None,
        hypothesis_registry: HypothesisRegistry | None = None,
        data_loader: ResearchDataLoader | None = None,
    ) -> None:
        self._candidates = candidate_registry or KnowledgeCandidateRegistry()
        self._hypotheses = hypothesis_registry or HypothesisRegistry()
        self._data = data_loader or ResearchDataLoader()
        self._data_sources: dict[str, bool] = {}

    def validate_all(self) -> CrossValidationReport:
        self._load_inputs()
        candidates = self._candidates.list_all()
        results: list[CandidateValidationResult] = []

        for candidate in candidates:
            results.append(self._validate_candidate(candidate))

        if not results:
            return CrossValidationReport(
                candidates_analyzed=0,
                most_robust_candidate_id="",
                weakest_candidate_id="",
                cross_regime_consistency_summary=NOT_AVAILABLE,
                cross_horizon_consistency_summary=NOT_AVAILABLE,
                cross_region_consistency_summary=NOT_AVAILABLE,
                recommended_follow_up_research=[
                    "No knowledge candidates to validate — run Sprint 5.3 / D5 promotion first.",
                ],
                candidate_results=[],
                data_sources=self._data_sources,
            )

        sorted_by_robust = sorted(results, key=lambda r: r.robustness_score, reverse=True)
        most_robust = sorted_by_robust[0]
        weakest = sorted_by_robust[-1]

        regime_summary = self._aggregate_consistency([r.regime_consistency for r in results])
        horizon_summary = self._aggregate_consistency([r.horizon_consistency for r in results])
        region_summary = self._aggregate_consistency([r.regional_consistency for r in results])

        follow_ups = self._build_follow_up_recommendations(results, regime_summary, region_summary)

        return CrossValidationReport(
            candidates_analyzed=len(results),
            most_robust_candidate_id=most_robust.candidate_id,
            weakest_candidate_id=weakest.candidate_id,
            cross_regime_consistency_summary=regime_summary,
            cross_horizon_consistency_summary=horizon_summary,
            cross_region_consistency_summary=region_summary,
            recommended_follow_up_research=follow_ups,
            candidate_results=results,
            data_sources=self._data_sources,
        )

    def _load_inputs(self) -> None:
        if not self._candidates.loaded_at_startup:
            self._candidates.load()
        if not self._hypotheses.loaded_at_startup:
            self._hypotheses.load()
        self._data_sources["tae_knowledge_candidates.json"] = self._candidates.count() > 0
        self._data_sources["tae_hypothesis_registry.json"] = self._hypotheses.count() > 0
        ensemble_ok = self._data.load()
        self._data_sources[str(DEFAULT_ENSEMBLE_PATH)] = ensemble_ok
        self._data_sources[str(REGIONAL_STRENGTH_PATH)] = REGIONAL_STRENGTH_PATH.is_file()
        self._data_sources[str(MULTI_HORIZON_PATH)] = MULTI_HORIZON_PATH.is_file()
        self._data_sources[str(HORIZON_VALIDATION_PATH)] = HORIZON_VALIDATION_PATH.is_file()

    def _validate_candidate(self, candidate: KnowledgeCandidate) -> CandidateValidationResult:
        hypothesis = self._hypotheses.get(candidate.source_hypothesis_id)
        notes: list[str] = []

        if hypothesis is None:
            notes.append(
                f"Hypothesis {candidate.source_hypothesis_id} missing from registry — "
                "cohort filters unavailable."
            )
            return CandidateValidationResult(
                candidate_id=candidate.candidate_id,
                source_hypothesis_id=candidate.source_hypothesis_id,
                title=candidate.title,
                regime_consistency=None,
                horizon_consistency=None,
                regional_consistency=None,
                robustness_score=0.0,
                confidence_adjustment=-10.0,
                validation_notes=" ".join(notes),
                regime_slices={r: DimensionSlice(label=r, status=NOT_AVAILABLE) for r in REGIMES},
                horizon_slices={h: DimensionSlice(label=h, status=NOT_AVAILABLE) for h in HORIZONS},
                region_slices={rg: DimensionSlice(label=rg, status=NOT_AVAILABLE) for rg in REGIONS},
            )

        matched = self._data.rows_matching(hypothesis)
        if not matched:
            notes.append("No ensemble cohort rows matched hypothesis conditions.")
            return CandidateValidationResult(
                candidate_id=candidate.candidate_id,
                source_hypothesis_id=candidate.source_hypothesis_id,
                title=candidate.title,
                regime_consistency=None,
                horizon_consistency=None,
                regional_consistency=None,
                robustness_score=0.0,
                confidence_adjustment=-10.0,
                validation_notes=" ".join(notes),
                regime_slices={r: DimensionSlice(label=r, status=NOT_AVAILABLE) for r in REGIMES},
                horizon_slices={h: DimensionSlice(label=h, status=NOT_AVAILABLE) for h in HORIZONS},
                region_slices={rg: DimensionSlice(label=rg, status=NOT_AVAILABLE) for rg in REGIONS},
            )

        regime_slices = self._evaluate_regimes(matched)
        horizon_slices, data_span_years = self._evaluate_horizons(matched)
        region_slices = self._evaluate_regions(matched, candidate)

        regime_consistency = self._consistency_score(
            [s.accuracy for s in regime_slices.values() if s.status == "EVALUATED"]
        )
        horizon_consistency = self._consistency_score(
            [s.accuracy for s in horizon_slices.values() if s.status == "EVALUATED"]
        )
        regional_accuracies = [
            s.accuracy for s in region_slices.values() if s.status == "EVALUATED"
        ]
        regional_consistency = self._consistency_score(regional_accuracies)

        if regime_consistency is None:
            notes.append("Regime dimension: NOT_AVAILABLE (insufficient multi-regime samples).")
        if horizon_consistency is None:
            notes.append("Horizon dimension: NOT_AVAILABLE (insufficient multi-horizon samples).")
        if regional_consistency is None:
            notes.append(
                "Regional dimension: Europe/UK NOT_AVAILABLE without hypothesis-linked "
                "regional signal CSVs; US evaluated when ensemble data present."
            )

        robustness = self._robustness_score(
            regime_consistency, horizon_consistency, regional_consistency, candidate
        )
        confidence_adj = self._confidence_adjustment(robustness, candidate.quality_score)

        notes.append(
            f"Validated {len(matched)} ensemble rows; data span ~{data_span_years:.1f} years. "
            "Research-only cross-validation — not trading authorization."
        )

        return CandidateValidationResult(
            candidate_id=candidate.candidate_id,
            source_hypothesis_id=candidate.source_hypothesis_id,
            title=candidate.title,
            regime_consistency=regime_consistency,
            horizon_consistency=horizon_consistency,
            regional_consistency=regional_consistency,
            robustness_score=robustness,
            confidence_adjustment=confidence_adj,
            validation_notes=" ".join(notes),
            regime_slices=regime_slices,
            horizon_slices=horizon_slices,
            region_slices=region_slices,
        )

    def _evaluate_regimes(self, rows: list[dict[str, str]]) -> dict[str, DimensionSlice]:
        slices: dict[str, DimensionSlice] = {}
        for regime in REGIMES:
            cohort = [
                r for r in rows
                if str(r.get("Market_Regime", "")).upper() == regime
            ]
            slices[regime] = self._slice_metrics(regime, cohort)
        return slices

    def _evaluate_horizons(self, rows: list[dict[str, str]]) -> tuple[dict[str, DimensionSlice], float]:
        dates: list[datetime] = []
        for row in rows:
            dt = self._parse_date(row.get("Signal_Date", ""))
            if dt is not None:
                dates.append(dt)

        if not dates:
            return {
                h: DimensionSlice(label=h, status=NOT_AVAILABLE) for h in HORIZONS
            }, 0.0

        max_date = max(dates)
        min_date = min(dates)
        span_years = (max_date - min_date).days / 365.25

        slices: dict[str, DimensionSlice] = {}
        for label, years in HORIZON_YEARS.items():
            if span_years < years - 0.5:
                slices[label] = DimensionSlice(label=label, status=NOT_AVAILABLE)
                continue
            try:
                cutoff = max_date.replace(year=max_date.year - years)
            except ValueError:
                cutoff = max_date.replace(year=max_date.year - years, day=28)
            cohort = [
                r for r in rows
                if self._parse_date(r.get("Signal_Date", "")) is not None
                and self._parse_date(r.get("Signal_Date", "")) >= cutoff
            ]
            slices[label] = self._slice_metrics(label, cohort)
        return slices, span_years

    def _evaluate_regions(
        self,
        rows: list[dict[str, str]],
        candidate: KnowledgeCandidate,
    ) -> dict[str, DimensionSlice]:
        slices: dict[str, DimensionSlice] = {}

        # US: ensemble cohort is US equities
        slices["US"] = self._slice_metrics("US", rows)

        # Europe / UK: no hypothesis-linked regional signal file in TAE research path
        slices["Europe"] = DimensionSlice(label="Europe", status=NOT_AVAILABLE)
        slices["UK"] = DimensionSlice(label="UK", status=NOT_AVAILABLE)

        if MULTI_HORIZON_PATH.is_file():
            eu_row = self._read_multi_horizon_row("EU")
            uk_row = self._read_multi_horizon_row("UK")
            if eu_row:
                slices["Europe"].status = "REFERENCE_ONLY"
            if uk_row:
                slices["UK"].status = "REFERENCE_ONLY"

        return slices

    def _slice_metrics(self, label: str, cohort: list[dict[str, str]]) -> DimensionSlice:
        if len(cohort) < MIN_SLICE_SAMPLE:
            return DimensionSlice(
                label=label,
                sample_size=len(cohort),
                status=NOT_AVAILABLE if len(cohort) == 0 else "INSUFFICIENT_SAMPLE",
            )

        wins = 0
        losses = 0
        returns: list[float] = []
        for row in cohort:
            forward = self._safe_float(row.get(FORWARD_RETURN_COL))
            if forward is None:
                win_raw = row.get("Win", "")
                if str(win_raw).lower() == "true":
                    wins += 1
                elif str(win_raw).lower() == "false":
                    losses += 1
                continue
            returns.append(forward)
            if forward > 0:
                wins += 1
            elif forward < 0:
                losses += 1

        decided = wins + losses
        if decided == 0:
            return DimensionSlice(label=label, sample_size=len(cohort), status=NOT_AVAILABLE)

        accuracy = wins / decided
        avg_ret = sum(returns) / len(returns) if returns else 0.0
        return DimensionSlice(
            label=label,
            sample_size=len(cohort),
            accuracy=accuracy,
            avg_forward_return=avg_ret,
            status="EVALUATED",
        )

    def _consistency_score(self, accuracies: list[float]) -> float | None:
        if len(accuracies) < 2:
            return None
        spread = max(accuracies) - min(accuracies)
        return round(max(0.0, 100.0 - spread * 100.0), 2)

    def _robustness_score(
        self,
        regime: float | None,
        horizon: float | None,
        regional: float | None,
        candidate: KnowledgeCandidate,
    ) -> float:
        weights: list[tuple[float, float]] = []
        if regime is not None:
            weights.append((regime, 0.35))
        if horizon is not None:
            weights.append((horizon, 0.35))
        if regional is not None:
            weights.append((regional, 0.20))

        if not weights:
            base = min(40.0, candidate.quality_score * 0.5)
            return round(base, 2)

        total_w = sum(w for _, w in weights)
        score = sum(v * w for v, w in weights) / total_w
        # Sample depth bonus from candidate evidence
        if candidate.sample_size >= 500:
            score += 5.0
        if candidate.sample_size >= 1500:
            score += 5.0
        return round(min(100.0, max(0.0, score)), 2)

    def _confidence_adjustment(self, robustness: float, quality: float) -> float:
        delta = (robustness - quality) * 0.15
        return round(max(-15.0, min(15.0, delta)), 2)

    def _aggregate_consistency(self, values: list[float | None]) -> str | float:
        present = [v for v in values if v is not None]
        if not present:
            return NOT_AVAILABLE
        return round(sum(present) / len(present), 2)

    def _build_follow_up_recommendations(
        self,
        results: list[CandidateValidationResult],
        regime_summary: str | float,
        region_summary: str | float,
    ) -> list[str]:
        follow_ups: list[str] = []

        if regime_summary == NOT_AVAILABLE:
            follow_ups.append(
                "Collect more BEAR/NEUTRAL cohort samples for discovery-derived hypotheses."
            )
        else:
            follow_ups.append(
                "Run dedicated cross-regime experiment matrix (BULL/BEAR/NEUTRAL) — research only."
            )

        if region_summary == NOT_AVAILABLE:
            follow_ups.append(
                "Add Europe/UK hypothesis-linked signal CSVs before regional candidate validation."
            )

        weak = min(results, key=lambda r: r.robustness_score)
        if weak.robustness_score < 55.0:
            follow_ups.append(
                f"Re-review weakest candidate {weak.candidate_id} "
                f"(robustness {weak.robustness_score:.1f}) under stricter cohort filters."
            )

        strong = max(results, key=lambda r: r.robustness_score)
        follow_ups.append(
            f"Prioritize follow-up research on {strong.candidate_id} "
            f"(robustness {strong.robustness_score:.1f}) — not live execution."
        )
        follow_ups.append(
            "Maintain RESEARCH_ONLY discipline — validation does not authorize broker or trading."
        )
        return follow_ups

    def _parse_date(self, value: str) -> datetime | None:
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        return None

    def _safe_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _read_multi_horizon_row(self, market: str) -> dict[str, str] | None:
        if not MULTI_HORIZON_PATH.is_file():
            return None
        try:
            with MULTI_HORIZON_PATH.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    if str(row.get("Market", "")).upper() == market.upper():
                        return dict(row)
        except (OSError, csv.Error) as exc:
            logger.warning("multi_horizon_backtest unreadable: %s", exc)
        return None
