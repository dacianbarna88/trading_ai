"""TAE CLI — opportunity-attrition command (upstream attrition audit)."""

from __future__ import annotations


def run(_args: list[str] | None = None) -> int:
    from tae_conversion_breakthrough import run_opportunity_attrition_breakthrough

    summary = run_opportunity_attrition_breakthrough(write_outputs=True)
    print(f"TAE Opportunity Attrition — {summary['verdict']}")
    print(f"Dominant upstream blocker: {summary.get('dominant_blocker') or 'NONE'}")
    print(f"Actionable conversion: {summary['actionable_conversion']:.1%}")
    print(f"policy_skip EV audit: {summary['policy_skip_ev_status']}")
    print(f"Deliverables: TAE_OPPORTUNITY_ATTRITION_AUDIT.md | TAE_OPPORTUNITY_DEATH_MAP.md | TAE_UPSTREAM_BLOCKER_CHALLENGER_REPORT.md")
    return 0
