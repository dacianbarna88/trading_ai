from datetime import datetime
from pathlib import Path

from data.storage import load_portfolio
from core.portfolio import get_open_positions

# Reducem poziții vechi care nu mai sunt în global radar, pentru test paper.
TO_REDUCE = ["UNH", "DIA", "MRK"]

portfolio = load_portfolio()
positions = get_open_positions(portfolio)

rows = []

for ticker in TO_REDUCE:
    if ticker not in positions:
        continue

    shares = positions[ticker]["shares"]
    avg_price = positions[ticker]["avg_price"]

    rows.append(
        f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")},{ticker},SELL,{avg_price},{shares},0,REBALANCE,EXTRA SLOT REDUCE SIMULATION,,,,,,,,\n'
    )

with Path("portfolio.csv").open("a") as f:
    f.writelines(rows)

print("Reduced:", [r.split(",")[1] for r in rows])
