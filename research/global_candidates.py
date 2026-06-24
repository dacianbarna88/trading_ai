from pathlib import Path
import pandas as pd

INPUT_FILE = "multi_market_candidates.csv"
OUTPUT_FILE = "global_candidates.csv"
GLOBAL_WATCHLIST_FILE = "watchlist_global.txt"


def main():
    path = Path(INPUT_FILE)

    if not path.exists():
        print(f"Lipsește {INPUT_FILE}. Rulează mai întâi multi_market_scanner.")
        return

    df = pd.read_csv(path)

    if df.empty:
        print("Nu există candidați globali.")
        return

    df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0)
    df["Allocation_Weight"] = pd.to_numeric(
        df.get("Allocation_Weight", 0),
        errors="coerce"
    ).fillna(0)

    df = df.sort_values(
        ["Score", "Allocation_Weight"],
        ascending=[False, False]
    )

    df.to_csv(OUTPUT_FILE, index=False)

    top = df.head(30)
    top["Ticker"].to_csv(GLOBAL_WATCHLIST_FILE, index=False, header=False)

    print()
    print("===== GLOBAL TOP OPPORTUNITIES =====")
    cols = [
        "Market", "Ticker", "Score", "Signal", "News_Bias",
        "Allocation_Weight", "Exit_Score", "Exit_Warning", "Market_Open"
    ]
    cols = [c for c in cols if c in df.columns]

    print(df[cols].head(20).to_string(index=False))
    print()
    print(f"Salvat: {OUTPUT_FILE}")
    print(f"Salvat: {GLOBAL_WATCHLIST_FILE}")


if __name__ == "__main__":
    main()
