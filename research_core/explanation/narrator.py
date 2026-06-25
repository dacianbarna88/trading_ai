"""Human-readable edge explanations."""

from __future__ import annotations

from research_core.types import Rule


class EdgeNarrator:
    """Produces audit-friendly explanations — extend templates in V3.1+."""

    def explain(
        self,
        rule: Rule,
        metrics: dict,
        baseline: dict,
        issues: list[str],
    ) -> str:
        parts = [
            f"Rule: {rule.description} ({rule.complexity} conditions).",
            f"Trades={metrics['Trades']} win={metrics['Win_Rate']}% avg={metrics['Avg_Return']}% "
            f"vs baseline avg={baseline['Avg_Return']}% (lift {metrics['Lift_vs_Baseline_Avg']}%).",
            f"Profit factor {metrics['Profit_Factor']} vs baseline {baseline['Profit_Factor']}.",
            f"Key features: {', '.join(sorted(rule.feature_groups))}.",
        ]
        if "RSI" in rule.description or "30_40" in rule.rule_id:
            parts.append("Prefers oversold RSI momentum bursts.")
        if "BEAR" in rule.description or "Regime_BEAR" in rule.rule_id:
            parts.append("Performs best when SPY is below SMA200 with negative 60d return.")
        if "Volume" in rule.description:
            parts.append("Volume profile is part of the filter.")
        if issues:
            parts.append(f"Caveats: {'; '.join(issues)}.")
        else:
            parts.append("Passed diversification and stability checks.")
        parts.append(
            "RESEARCH ONLY — requires explicit human approval before any production use."
        )
        return " ".join(parts)
