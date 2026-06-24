import json
from pathlib import Path

CURRENT = {
    "US": 47.4,
    "EU": 42.1,
    "UK": 10.5,
}

CURRENT_STRATEGIC_SCORE = 43.7
CURRENT_ALLOCATOR_HEALTH = 47.4

adaptive = json.loads(
    Path("adaptive_allocation.json").read_text()
)

target = adaptive["recommended_allocation"]

alignment_before = 100 - (
    abs(CURRENT["US"] - target["US"])
    + abs(CURRENT["EU"] - target["EU"])
    + abs(CURRENT["UK"] - target["UK"])
)

alignment_after = 100

projected_score = round(
    CURRENT_STRATEGIC_SCORE + (alignment_after - alignment_before) * 0.5,
    2
)

projected_health = round(
    CURRENT_ALLOCATOR_HEALTH + (alignment_after - alignment_before) * 0.4,
    2
)

result = {
    "current_allocation": CURRENT,
    "recommended_allocation": target,
    "alignment_before": round(alignment_before, 2),
    "alignment_after": round(alignment_after, 2),
    "projected_strategic_score": projected_score,
    "projected_allocator_health": projected_health,
}

Path("strategic_rebalance_simulation.json").write_text(
    json.dumps(result, indent=2)
)

summary = f"""
===== STRATEGIC REBALANCE SIMULATOR =====

Current Strategic Score:
{CURRENT_STRATEGIC_SCORE}

Projected Strategic Score:
{projected_score}

Current Allocator Health:
{CURRENT_ALLOCATOR_HEALTH}

Projected Allocator Health:
{projected_health}

Alignment Before:
{round(alignment_before,2)}

Alignment After:
{alignment_after}

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path("strategic_rebalance_summary.txt").write_text(
    summary.strip()
)

print(summary)
