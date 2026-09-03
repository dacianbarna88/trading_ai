import pandas as pd

from config.allocation_settings import (
    MAX_MIGRATION_PCT,
    CORE_US_TICKERS,
    MIN_CORE_US_EXPOSURE_PCT,
    MIN_GLOBAL_RANK_SCORE,
)
from core.market_sessions import get_ticker_region
from core.portfolio import open_buy_row_mask

transfer = pd.read_csv("capital_transfer_plan.csv")
reduce_df = pd.read_csv("capital_reduce_candidates.csv")
add_df = pd.read_csv("capital_add_candidates.csv")
gap_df = pd.read_csv("allocation_gap.csv")

# Summing Current_Value across every row double-counts: SELL rows carry
# sale proceeds in Current_Value, and a closed-then-reopened ticker leaves
# a stale closed BUY row alongside the fresh one. Only open BUY rows
# represent value still held.
_portfolio = pd.read_csv("portfolio.csv")
_portfolio["Current_Value"] = pd.to_numeric(_portfolio["Current_Value"], errors="coerce")
_open_mask = open_buy_row_mask(_portfolio)
portfolio_value = float(_portfolio.loc[_open_mask, "Current_Value"].fillna(0).sum())

# Every reduce candidate here is a US ticker (capital_migration_candidates.py
# only proposes US positions for REDUCE), and CORE_US_TICKERS is excluded
# below - so every dollar sold in this plan comes out of total US exposure.
# Cap total reductions so US exposure can never drop below its configured
# floor, regardless of how attractive the EU/UK candidates look.
current_us_value = float(
    _portfolio.loc[_open_mask].assign(
        _region=lambda d: d["Ticker"].map(get_ticker_region)
    ).pipe(lambda d: d.loc[d["_region"] == "US", "Current_Value"]).fillna(0).sum()
)
min_us_value_floor = portfolio_value * MIN_CORE_US_EXPOSURE_PCT / 100
us_exposure_headroom = max(0.0, current_us_value - min_us_value_floor)

max_cycle = round(
    portfolio_value * MAX_MIGRATION_PCT / 100,
    2
)

reduce_df = reduce_df[
    ~reduce_df["Ticker"].isin(CORE_US_TICKERS)
]

add_df = add_df[
    add_df["Global_Rank_Score"] >= MIN_GLOBAL_RANK_SCORE
]

remaining = min(max_cycle, round(us_exposure_headroom, 2))

sell_rows = []

for _, row in reduce_df.iterrows():

    if remaining <= 0:
        break

    amount = min(
        float(row["Position_Value"]),
        remaining
    )

    sell_rows.append({
        "Action": "SELL",
        "Ticker": row["Ticker"],
        "Amount_$": round(amount, 2)
    })

    remaining -= amount

buy_rows = []

qualified = add_df.sort_values(
    "Global_Rank_Score",
    ascending=False
)

sell_total = sum(row["Amount_$"] for row in sell_rows)

if len(qualified) > 0 and sell_total > 0:

    per_position = round(
        sell_total / len(qualified),
        2
    )

    for _, row in qualified.iterrows():

        buy_rows.append({
            "Action": "BUY",
            "Ticker": row["Ticker"],
            "Market": row["Market"],
            "Amount_$": per_position
        })

result = pd.DataFrame(
    sell_rows + buy_rows
)

result.to_csv(
    "safe_migration_plan.csv",
    index=False
)

print("\n===== SAFE MIGRATION PLAN =====\n")
print(result.to_string(index=False))
print()
print("Portfolio Value:", round(portfolio_value, 2))
print("Max Cycle:", max_cycle)
print("Protected Core:", CORE_US_TICKERS)
print()
print("Current US Exposure:", round(current_us_value, 2))
print(f"Min US Exposure Floor ({MIN_CORE_US_EXPOSURE_PCT}%):", round(min_us_value_floor, 2))
print("US Exposure Headroom:", round(us_exposure_headroom, 2))
if us_exposure_headroom < max_cycle:
    print(
        f"NOTE: reduce amount capped by the {MIN_CORE_US_EXPOSURE_PCT}% US exposure floor "
        f"(would otherwise have used the full {max_cycle} migration budget)."
    )
