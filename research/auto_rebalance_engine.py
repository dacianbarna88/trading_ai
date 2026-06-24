import pandas as pd
from pathlib import Path

REBALANCE_FILE = "global_rebalance_recommendations.csv"
GLOBAL_FILE = "global_candidates.csv"


def get_auto_rebalance_plan():
    if not Path(REBALANCE_FILE).exists() or not Path(GLOBAL_FILE).exists():
        return {"reduce": [], "buy": []}

    rebalance = pd.read_csv(REBALANCE_FILE)
    global_df = pd.read_csv(GLOBAL_FILE)

    reduce_list = rebalance[rebalance["Action"].astype(str) == "REDUCE"]["Ticker"].astype(str).head(5).tolist()
    buy_list = global_df[global_df["Signal"].astype(str) == "STRONG BUY"].sort_values("Score", ascending=False)["Ticker"].astype(str).head(5).tolist()

    return {"reduce": reduce_list, "buy": buy_list}


def main():

    if not Path(REBALANCE_FILE).exists():
        print("Lipsește global_rebalance_recommendations.csv")
        return

    if not Path(GLOBAL_FILE).exists():
        print("Lipsește global_candidates.csv")
        return

    rebalance = pd.read_csv(REBALANCE_FILE)
    global_df = pd.read_csv(GLOBAL_FILE)

    reduce_df = rebalance[
        rebalance["Action"].astype(str) == "REDUCE"
    ]

    buy_df = global_df[
        global_df["Signal"].astype(str) == "STRONG BUY"
    ]

    print()
    print("===== AUTO REBALANCE PLAN =====")

    print()
    print("REDUCE:")
    if reduce_df.empty:
        print("NONE")
    else:
        print(
            reduce_df[
                ["Ticker","Score"]
            ].to_string(index=False)
        )

    print()
    print("TOP GLOBAL BUYS:")
    if buy_df.empty:
        print("NONE")
    else:
        print(
            buy_df[
                ["Market","Ticker","Score"]
            ]
            .sort_values("Score", ascending=False)
            .head(10)
            .to_string(index=False)
        )

    print()

if __name__ == "__main__":
    main()
