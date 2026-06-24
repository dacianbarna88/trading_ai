import pandas as pd
from pathlib import Path

REGISTRY_FILE = "decision_registry.csv"

if not Path(REGISTRY_FILE).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY_FILE)

defaults = {
    "Ticker": "SPY",
    "Entry_Price": 0.0,
    "Evaluation_Days": 5,
    "Target_Return_%": 2.0,
    "Stop_Return_%": -2.0,
}

for col, value in defaults.items():
    if col not in df.columns:
        df[col] = value

df.to_csv(REGISTRY_FILE, index=False)

print("===== V28.6 DECISION REGISTRY ENRICHMENT =====")
print()
print(df.to_string(index=False))
print()
print("decision_registry.csv enriched")
