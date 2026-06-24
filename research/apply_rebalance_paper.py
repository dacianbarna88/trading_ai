from datetime import datetime
from pathlib import Path
import pandas as pd

from data.storage import load_portfolio
from core.portfolio import get_open_positions

REBALANCE_FILE = "global_rebalance_recommendations.csv"
PORTFOLIO_FILE = "portfolio.csv"

def main():
    portfolio = load_portfolio()
    positions = get_open_positions(portfolio)
    rebalance = pd.read_csv(REBALANCE_FILE)

    reduce_list = rebalance[rebalance["Action"].astype(str) == "REDUCE"]["Ticker"].astype(str).tolist()

    rows = []

    for ticker in reduce_list:
        if ticker not in positions:
            continue

        shares = positions[ticker]["shares"]
        avg_price = positions[ticker]["avg_price"]

        rows.append(
            f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")},{ticker},SELL,{avg_price},{shares},0,REBALANCE,GLOBAL REDUCE SIMULATION,,,,,,,,\n'
        )

    if not rows:
        print("Nu am aplicat SELL-uri.")
        return

    with Path(PORTFOLIO_FILE).open("a") as f:
        f.writelines(rows)

    print("SELL paper aplicat pentru:")
    for r in rows:
        print(r.split(",")[1])

if __name__ == "__main__":
    main()
