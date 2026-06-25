"""Edge confidence scoring."""

from __future__ import annotations

from research_core.config.discovery import DiscoveryConfig


class EdgeConfidenceScorer:
    """Weighted confidence score — adjust weights via ResearchConfig."""

    def __init__(self, config: DiscoveryConfig) -> None:
        self._weights = config.confidence_weights

    def score(
        self,
        robustness: float,
        wf_score: float,
        trades: int,
        sector_diversity: int,
        lift: float,
        pf: float,
        baseline_pf: float,
    ) -> float:
        w = self._weights
        trade_score = min(trades / 300.0, 1.0) * 100.0
        sector_score = min(sector_diversity / 6.0, 1.0) * 100.0
        perf_score = (
            min(max(lift, 0) / 15.0, 1.0) * 50
            + min(max(pf - baseline_pf, 0) / 2.0, 1.0) * 50
        )
        total = (
            robustness * w["robustness"]
            + wf_score * w["walk_forward"]
            + trade_score * w["trade_count"]
            + sector_score * w["sector_diversity"]
            + perf_score * w["performance"]
        )
        return round(min(total, 100.0), 2)
