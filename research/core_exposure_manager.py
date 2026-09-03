import pandas as pd
from data.storage import load_portfolio
from core.portfolio import get_open_positions
from core.market_sessions import get_ticker_region

positions = get_open_positions(load_portfolio())

market_value = {
    "US": 0.0,
    "EU": 0.0,
    "UK": 0.0,
}

for ticker, pos in positions.items():

    value = float(pos["shares"]) * float(pos["avg_price"])

    # A plain .PA/.DE-only EU check and "everything else is US" fallback
    # misclassified other EU exchanges (.AS/.MI/.SW/.MC/.BR) and Asia
    # tickers as US exposure, skewing this exposure breakdown. Regions
    # outside the US/EU/UK target set here (e.g. ASIA) are excluded
    # rather than folded into US.
    region = get_ticker_region(ticker)
    if region in market_value:
        market_value[region] += value

total = sum(market_value.values())

rows = []

for market, value in market_value.items():

    pct = 0

    if total > 0:
        pct = round(value / total * 100, 1)

    rows.append({
        "Market": market,
        "Exposure_$": round(value, 2),
        "Exposure_%": pct
    })

df = pd.DataFrame(rows)

df.to_csv(
    "core_exposure_report.csv",
    index=False
)

print("\n===== CORE EXPOSURE REPORT =====\n")
print(df.to_string(index=False))
print()
print("Portfolio Exposure:", round(total, 2))
