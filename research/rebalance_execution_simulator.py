import pandas as pd

REBALANCE_FILE = "global_rebalance_recommendations.csv"
GLOBAL_FILE = "global_candidates.csv"

def main():

    rebalance = pd.read_csv(REBALANCE_FILE)
    global_df = pd.read_csv(GLOBAL_FILE)

    reduce_df = rebalance[
        rebalance["Action"].astype(str) == "REDUCE"
    ]

    buy_df = global_df[
        global_df["Signal"].astype(str) == "STRONG BUY"
    ].sort_values("Score", ascending=False)

    print()
    print("===== REBALANCE EXECUTION SIMULATION =====")

    slots_freed = len(reduce_df)

    print()
    print("SELL / REDUCE:")
    if reduce_df.empty:
        print("NONE")
    else:
        print(
            reduce_df[
                ["Ticker","Score"]
            ].to_string(index=False)
        )

    print()
    print("NEW BUY CAPACITY:", slots_freed)

    print()
    print("NEW BUYS:")

    if buy_df.empty:
        print("NONE")
    else:
        print(
            buy_df.head(slots_freed)[
                ["Market","Ticker","Score"]
            ].to_string(index=False)
        )

if __name__ == "__main__":
    main()
