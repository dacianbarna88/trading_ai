"""The validation gates, applied the same way to every candidate."""

from __future__ import annotations

from dataclasses import dataclass

from tae2 import config


@dataclass(frozen=True)
class Check:
    gate: str
    passed: bool
    detail: str


def evaluate(
    cand: dict[str, float],
    bench: dict[str, float],
    deflated_sharpe: float,
    cost_bps: float,
    gates: config.Gates = config.GATES,
) -> list[Check]:
    """`cand` / `bench` are stats.summary() dicts computed with the same split."""
    checks = [
        Check("history", cand["years"] >= gates.min_years, f"{cand['years']:.1f} years (need {gates.min_years:g})"),
        Check("costs", cost_bps >= gates.min_cost_bps, f"{cost_bps:g} bps per dollar traded (need {gates.min_cost_bps:g})"),
    ]
    if gates.beat_benchmark_both_halves:
        first = cand["sharpe_first_half"] > bench["sharpe_first_half"]
        second = cand["sharpe_second_half"] > bench["sharpe_second_half"]
        checks.append(
            Check(
                "beats benchmark, both halves",
                first and second,
                f"Sharpe {cand['sharpe_first_half']:.2f} vs {bench['sharpe_first_half']:.2f}, "
                f"then {cand['sharpe_second_half']:.2f} vs {bench['sharpe_second_half']:.2f}",
            )
        )
    if gates.max_drawdown_vs_benchmark:
        checks.append(
            Check(
                "drawdown no worse",
                cand["max_dd"] >= bench["max_dd"],
                f"{cand['max_dd']:.1%} vs {bench['max_dd']:.1%}",
            )
        )
    checks.append(
        Check(
            "deflated Sharpe",
            deflated_sharpe >= gates.min_deflated_sharpe,
            f"{deflated_sharpe:.2f} (need {gates.min_deflated_sharpe:.2f})",
        )
    )
    return checks


def passed(checks: list[Check]) -> bool:
    return all(c.passed for c in checks)
