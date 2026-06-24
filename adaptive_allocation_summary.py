import json
from pathlib import Path

data = json.loads(Path("adaptive_allocation.json").read_text())

strength = data["strength"]
raw = data["raw_allocation"]
recommended = data["recommended_allocation"]

summary = f"""
===== ADAPTIVE ALLOCATION ENGINE =====

Regional Strength:
US: {strength["US"]}
EU: {strength["EU"]}
UK: {strength["UK"]}

Raw Allocation:
US: {raw["US"]}%
EU: {raw["EU"]}%
UK: {raw["UK"]}%

Recommended Allocation:
US: {recommended["US"]}%
EU: {recommended["EU"]}%
UK: {recommended["UK"]}%

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path("adaptive_allocation_summary.txt").write_text(summary.strip())

print("adaptive_allocation_summary.txt updated")
print(summary)
