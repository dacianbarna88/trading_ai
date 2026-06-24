import json
from pathlib import Path

CURRENT_ALLOCATION = {
    "US": 47.4,
    "EU": 42.1,
    "UK": 10.5,
}

data = json.loads(Path("adaptive_allocation.json").read_text())
recommended = data["recommended_allocation"]

gaps = {}

for region, current in CURRENT_ALLOCATION.items():
    target = recommended.get(region, 0)
    gap = round(target - current, 2)

    if gap > 0:
        action = "INCREASE"
    elif gap < 0:
        action = "DECREASE"
    else:
        action = "HOLD"

    gaps[region] = {
        "current": current,
        "recommended": target,
        "gap": gap,
        "action": action,
    }

Path("allocation_gap_analysis.json").write_text(
    json.dumps(gaps, indent=2)
)

summary_lines = [
    "===== ALLOCATION GAP ANALYZER =====",
    "",
]

for region, row in gaps.items():
    summary_lines.append(
        f"{region}: Current {row['current']}% | "
        f"Recommended {row['recommended']}% | "
        f"Gap {row['gap']}% | "
        f"Action {row['action']}"
    )

summary_lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

summary = "\n".join(summary_lines)

Path("allocation_gap_summary.txt").write_text(summary)

print("allocation_gap_analysis.json updated")
print("allocation_gap_summary.txt updated")
print(summary)
