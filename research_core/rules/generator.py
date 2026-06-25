"""Automatic rule generation from binned features."""

from __future__ import annotations

import itertools

import pandas as pd

from research_core.config.discovery import DiscoveryConfig
from research_core.types import Rule


class BinRuleGenerator:
    """
    Generates single, pair, and triple bin-conjunction rules.
    V3.1 can subclass or replace with alternative discovery algorithms.
    """

    def __init__(self, config: DiscoveryConfig, column_groups: dict[str, str]) -> None:
        self._config = config
        self._column_groups = column_groups

    def generate(self, df: pd.DataFrame) -> list[Rule]:
        singles = self._single_rules(df)
        rules = list(singles)
        max_combo = self._config.max_feature_combinations

        if max_combo >= 2:
            single_by_group: dict[str, list[Rule]] = {}
            for rule in singles:
                for g in rule.feature_groups:
                    single_by_group.setdefault(g, []).append(rule)

            groups = list(single_by_group.keys())
            cap = self._config.max_rules_per_group_pair
            for g1, g2 in itertools.combinations(groups, 2):
                for r1 in single_by_group[g1][:cap]:
                    for r2 in single_by_group[g2][:cap]:
                        rules.append(self._combine(r1, r2, "P"))

        if max_combo >= 3 and self._config.enable_three_feature_rules:
            single_by_group = {}
            for rule in singles:
                for g in rule.feature_groups:
                    single_by_group.setdefault(g, []).append(rule)
            groups = list(single_by_group.keys())
            pair_rules = [r for r in rules if r.complexity == 2]
            for p in pair_rules[: self._config.max_pair_rules_for_triples]:
                used = p.feature_groups
                for g in groups:
                    if g in used:
                        continue
                    for r3 in single_by_group[g][: self._config.max_triples_per_group]:
                        rules.append(self._combine_pair_triple(p, r3))

        return rules

    def _single_rules(self, df: pd.DataFrame) -> list[Rule]:
        singles: list[Rule] = []
        min_count = self._config.min_single_bin_trades
        for col in [c for c in df.columns if c.startswith("BIN_")]:
            count = int(df[col].sum())
            if count < min_count:
                continue
            grp = self._column_groups.get(col, "Other")
            desc = col.replace("BIN_", "").replace("_", " ")
            singles.append(
                Rule(
                    rule_id=f"S_{col}",
                    description=desc,
                    bin_columns=(col,),
                    complexity=1,
                    feature_groups=frozenset({grp}),
                )
            )
        return singles

    def _combine(self, r1: Rule, r2: Rule, prefix: str) -> Rule:
        cols = r1.bin_columns + r2.bin_columns
        return Rule(
            rule_id=f"{prefix}_{r1.rule_id}_{r2.rule_id}",
            description=f"{r1.description} AND {r2.description}",
            bin_columns=cols,
            complexity=r1.complexity + r2.complexity,
            feature_groups=r1.feature_groups | r2.feature_groups,
        )

    def _combine_pair_triple(self, pair: Rule, r3: Rule) -> Rule:
        return Rule(
            rule_id=f"T_{pair.rule_id}_{r3.rule_id}",
            description=f"{pair.description} AND {r3.description}",
            bin_columns=pair.bin_columns + r3.bin_columns,
            complexity=3,
            feature_groups=pair.feature_groups | r3.feature_groups,
        )
