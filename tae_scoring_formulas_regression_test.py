#!/usr/bin/env python3
"""
TAE Scoring Formulas Regression Test — allocation/prioritization edge cases.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Covers two previously-dead-code bugs fixed in this codebase:
- core/allocation_learning.py: normalize_scores/apply_allocation_bounds
  crashed (ZeroDivisionError / AttributeError) on empty input instead of
  returning {}.
- research_core/autonomy/research_prioritizer.py: scientific_value was
  computed and shown in reports but never actually affected the ranking
  score (VALUE_SCORE was declared but unused).
"""

from __future__ import annotations

import sys

from core.allocation_learning import apply_allocation_bounds, normalize_scores
from research_core.autonomy.research_prioritizer import (
    VALUE_SCORE,
    ResearchPrioritizer,
    _OpportunityDraft,
)


def test_normalize_scores_empty_input_returns_empty_dict() -> None:
    assert normalize_scores({}) == {}


def test_normalize_scores_all_zero_splits_equally() -> None:
    result = normalize_scores({"US": 0, "EU": 0})
    assert result == {"US": 50.0, "EU": 50.0}


def test_normalize_scores_basic_proportion() -> None:
    result = normalize_scores({"US": 75, "EU": 25})
    assert result == {"US": 75.0, "EU": 25.0}


def test_apply_allocation_bounds_empty_input_returns_empty_dict() -> None:
    assert apply_allocation_bounds({}, {}, {}) == {}


def test_apply_allocation_bounds_respects_min_max() -> None:
    weights = {"US": 90.0, "EU": 5.0, "UK": 5.0}
    min_allocations = {"US": 45, "EU": 15, "UK": 5}
    max_allocations = {"US": 80, "EU": 40, "UK": 15}

    bounded = apply_allocation_bounds(weights, min_allocations, max_allocations)

    assert bounded["US"] <= 80
    assert bounded["EU"] >= 15
    assert abs(sum(bounded.values()) - 100) < 0.02


def _draft(**overrides) -> _OpportunityDraft:
    base = dict(
        opportunity_id="opp-1",
        source_type="discovery",
        source_id="src-1",
        title="test",
        why_it_matters="test",
        suggested_next_action="investigate",
        novelty=50.0,
        evidence_quality=50.0,
        robustness=50.0,
        validation_gap_score=0.0,
        information_gain=50.0,
        duplicate_risk=0.0,
        research_cost=35.0,
        scientific_value="MEDIUM",
    )
    base.update(overrides)
    return _OpportunityDraft(**base)


def test_scientific_value_changes_ranking_score() -> None:
    prioritizer = ResearchPrioritizer()

    low = prioritizer._score_opportunity(_draft(scientific_value="LOW"))
    medium = prioritizer._score_opportunity(_draft(scientific_value="MEDIUM"))
    high = prioritizer._score_opportunity(_draft(scientific_value="HIGH"))

    assert low.priority_score < medium.priority_score < high.priority_score

    expected_gap = round((VALUE_SCORE["HIGH"] - VALUE_SCORE["LOW"]) * 0.14, 2)
    actual_gap = round(high.priority_score - low.priority_score, 2)
    assert actual_gap == expected_gap


def main() -> int:
    tests = [
        test_normalize_scores_empty_input_returns_empty_dict,
        test_normalize_scores_all_zero_splits_equally,
        test_normalize_scores_basic_proportion,
        test_apply_allocation_bounds_empty_input_returns_empty_dict,
        test_apply_allocation_bounds_respects_min_max,
        test_scientific_value_changes_ranking_score,
    ]

    failed = 0
    for test in tests:
        name = test.__name__
        try:
            test()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")

    print(f"\nResult: {len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
