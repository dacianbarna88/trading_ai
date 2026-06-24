import json
from pathlib import Path

from core.allocation_learning import recommend_allocation

BACKTEST_RESULTS = {
    "US": {"2Y": 40.07, "5Y": 86.75, "10Y": 318.84},
    "EU": {"2Y": 39.08, "5Y": 49.98, "10Y": 162.65},
    "UK": {"2Y": 42.72, "5Y": 67.32, "10Y": 125.90},
}

result = recommend_allocation(BACKTEST_RESULTS)

Path("adaptive_allocation.json").write_text(
    json.dumps(result, indent=2)
)

print("adaptive_allocation.json updated")
print(result)
