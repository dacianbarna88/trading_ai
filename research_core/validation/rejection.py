"""Rejection pipeline — register new rejection checks in V3.1+."""

from __future__ import annotations

from typing import Callable

from research_core.config.discovery import DiscoveryConfig


class RejectionPipeline:
    """Ordered rejection checks with auditable reasons."""

    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config
        self._checks: list[tuple[str, Callable[[dict, dict], bool]]] = [
            ("Low_Sample", self._low_sample),
            ("Poor_Robustness", self._poor_robustness),
            ("Ticker_Concentration", self._ticker_concentration),
            ("Sector_Concentration", self._sector_concentration),
            ("Walk_Forward_Failure", self._walk_forward_failure),
            ("Overfitting", self._overfitting),
        ]

    def reason(self, metrics: dict, baseline: dict, issues: list[str]) -> str | None:
        ctx = {"issues": issues}
        metrics_with_ctx = {**metrics, "_issues": issues}
        for name, check in self._checks:
            if check(metrics_with_ctx, baseline):
                return name
        return None

    def _low_sample(self, m: dict, _b: dict) -> bool:
        return m["Trades"] < self._config.min_trades

    def _poor_robustness(self, m: dict, b: dict) -> bool:
        cfg = self._config
        if m.get("Lift_vs_Baseline_Avg") is None or m["Lift_vs_Baseline_Avg"] < cfg.min_lift_pct:
            return True
        if m.get("Profit_Factor") is None or m["Profit_Factor"] < b["Profit_Factor"]:
            return True
        if m.get("Worst_Trade") is not None and m["Worst_Trade"] < b["Worst_Trade"] - 5:
            return True
        if m.get("Avg_Return") and m.get("Median_Return"):
            if m["Avg_Return"] - m["Median_Return"] > cfg.unstable_gap:
                return True
        return False

    def _ticker_concentration(self, m: dict, _b: dict) -> bool:
        return any("ticker_concentration" in x for x in m.get("_issues", []))

    def _sector_concentration(self, m: dict, _b: dict) -> bool:
        issues = m.get("_issues", [])
        return any("sector" in x for x in issues)

    def _walk_forward_failure(self, m: dict, _b: dict) -> bool:
        valid = m.get("Walk_Forward_Valid_Splits", 0)
        if valid == 0:
            return True
        rate = m["Walk_Forward_Passes"] / valid
        return rate < self._config.min_wf_pass_rate

    def _overfitting(self, m: dict, _b: dict) -> bool:
        issues = m.get("_issues", [])
        return any("ticker_split" in x or "time_window" in x for x in issues)
