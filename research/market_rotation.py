from pathlib import Path
import pandas as pd


INPUT_FILE = "global_candidates.csv"


SECTOR_MAP = {
    "AAPL": "US_TECH",
    "MSFT": "US_TECH",
    "NVDA": "US_TECH",
    "QQQ": "US_TECH",

    "SPY": "US_INDEX",

    "MC.PA": "EU_LUXURY",
    "AIR.PA": "EU_INDUSTRIAL",
    "SAP.DE": "EU_TECH",
    "SIE.DE": "EU_INDUSTRIAL",
    "ALV.DE": "EU_FINANCIAL",

    "HSBA.L": "UK_FINANCIAL",
    "SHEL.L": "UK_ENERGY",
    "BP.L": "UK_ENERGY",
    "ULVR.L": "UK_CONSUMER",
    "AZN.L": "UK_HEALTHCARE",
}


def main():
    path = Path(INPUT_FILE)

    if not path.exists():
        print("Lipsește global_candidates.csv")
        return

    df = pd.read_csv(path)

    df["Sector"] = df["Ticker"].map(
        lambda x: SECTOR_MAP.get(str(x).upper(), "OTHER")
    )

    rotation = (
        df.groupby("Sector")["Score"]
        .mean()
        .reset_index()
        .sort_values("Score", ascending=False)
    )

    rotation.to_csv(
        "market_rotation.csv",
        index=False
    )

    print()
    print("===== MARKET ROTATION =====")
    print(rotation.to_string(index=False))
    print()
    print("Salvat: market_rotation.csv")


if __name__ == "__main__":
    main()
