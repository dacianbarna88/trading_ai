"""
Strategy Candidate Builder — Phase X Sprint X.3A

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Builds canonical discovery candidates from deterministic hypotheses.
"""

from __future__ import annotations

import logging
from pathlib import Path

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_discovery.strategy_discovery_report import (
    DiscoveryCandidate,
    StrategyDiscoveryReport,
    StrategyDiscoveryVerdict,
)
from research_core.strategy_discovery.strategy_feature_library import (
    get_feature_library,
    validate_feature_library,
)
from research_core.strategy_discovery.strategy_hypothesis_generator import (
    TARGET_HYPOTHESIS_COUNT,
    StrategyHypothesis,
    generate_hypotheses,
)

logger = logging.getLogger(__name__)


def build_candidates(hypotheses: list[StrategyHypothesis]) -> list[DiscoveryCandidate]:
    candidates: list[DiscoveryCandidate] = []
    for hypothesis in hypotheses:
        candidates.append(
            DiscoveryCandidate(
                discovery_id=hypothesis.discovery_id,
                entry_rule=hypothesis.entry_rule,
                exit_rule=hypothesis.exit_rule,
                market_filter=hypothesis.market_filter,
                holding_period=hypothesis.holding_period,
                risk_profile=hypothesis.risk_profile,
                confidence_seed=hypothesis.confidence_seed,
                feature_vector=list(hypothesis.feature_vector),
            )
        )
    return candidates


class StrategyDiscoveryEngine:
    """Generates new research-only strategy candidates — no execution."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._warnings: list[str] = []

    def discover(self) -> StrategyDiscoveryReport:
        before_mtimes = self._snapshot_mtimes()
        library_ok, library_warnings = validate_feature_library()
        self._warnings.extend(library_warnings)

        feature_library = get_feature_library()
        hypotheses = generate_hypotheses(TARGET_HYPOTHESIS_COUNT)
        candidates = build_candidates(hypotheses)

        if len(candidates) < TARGET_HYPOTHESIS_COUNT:
            self._warnings.append(
                f"Generated {len(candidates)} candidates; expected {TARGET_HYPOTHESIS_COUNT}"
            )

        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)
        if not protected_ok:
            self._warnings.append("Protected file mtimes changed during strategy discovery")

        verdict = self._determine_verdict(library_ok, candidates)
        avg_confidence = (
            sum(candidate.confidence_seed for candidate in candidates) / len(candidates)
            if candidates
            else 0.0
        )

        return StrategyDiscoveryReport(
            verdict=verdict,
            candidates=candidates,
            feature_library=feature_library,
            hypothesis_count=len(hypotheses),
            candidate_count=len(candidates),
            average_confidence_seed=round(avg_confidence, 4),
            warnings=list(self._warnings),
            protected_files_unchanged=protected_ok,
        )

    def _determine_verdict(
        self,
        library_ok: bool,
        candidates: list[DiscoveryCandidate],
    ) -> StrategyDiscoveryVerdict:
        if not library_ok:
            return StrategyDiscoveryVerdict.STRATEGY_DISCOVERY_INSUFFICIENT_FEATURES

        if not candidates:
            return StrategyDiscoveryVerdict.STRATEGY_DISCOVERY_INSUFFICIENT_FEATURES

        if self._warnings or len(candidates) < TARGET_HYPOTHESIS_COUNT:
            return StrategyDiscoveryVerdict.STRATEGY_DISCOVERY_READY_WITH_WARNINGS

        return StrategyDiscoveryVerdict.STRATEGY_DISCOVERY_FOUNDATION_READY

    def _snapshot_mtimes(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for rel in PROTECTED_PATHS:
            full = self._root / rel
            if full.is_file():
                snapshot[str(rel)] = full.stat().st_mtime
        return snapshot

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
