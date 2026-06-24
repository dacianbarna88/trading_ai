import pandas as pd
from pathlib import Path

from data.storage import load_portfolio
from core.portfolio import get_open_positions

CANDIDATES_FILE = "global_candidates.csv"
OUTPUT_FILE = "global_rebalance_recommendations.csv"


def main():
    if not Path(CANDIDATES_FILE).exists():
        print("Lipsește global_candidates.csv")
        return

    portfolio = load_portfolio()
    positions = get_open_positions(portfolio)
    candidates = pd.read_csv(CANDIDATES_FILE)

    rows = []

    for ticker in positions.keys():
        row = candidates[candidates["Ticker"].astype(str).str.upper() == ticker.upper()]

        if row.empty:
            rows.append({
                "Ticker": ticker,
                "Action": "REVIEW",
                "Reason": "Not in global candidates",
                "Score": "",
                "Exit_Warning": "",
                "Market": "",
            })
            continue

        r = row.iloc[0]
        score = float(r.get("Score", 0))
        exit_warning = str(r.get("Exit_Warning", "False")).upper() == "TRUE"

        action = "HOLD"
        reason = "OK"

        if exit_warning and score < 80:
            action = "REDUCE"
            reason = "Exit warning + weak global score"

        rows.append({
            "Ticker": ticker,
            "Action": action,
            "Reason": reason,
            "Score": score,
            "Exit_Warning": exit_warning,
            "Market": r.get("Market", ""),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)

    print()
    print("===== GLOBAL REBALANCE RECOMMENDATIONS =====")
    print(df.to_string(index=False))
    print()
    print(f"Salvat: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
