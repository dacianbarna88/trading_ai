"""Deterministic rule list capping for safe first runs."""

from __future__ import annotations

from research_core.types import Rule


def cap_rules_deterministic(rules: list[Rule], max_count: int | None) -> tuple[list[Rule], bool, int]:
    """
    Cap rules by sorted rule_id for reproducible sampling.
    Returns (rules, was_capped, original_count).
    """
    original = len(rules)
    if max_count is None or max_count <= 0 or original <= max_count:
        return rules, False, original
    capped = sorted(rules, key=lambda rule: rule.rule_id)[:max_count]
    return capped, True, original
