from pathlib import Path
import pandas as pd

ROTATION_FILE = "market_rotation_summary.txt"
REGIME_FILE = "cross_market_regime.csv"


def main():

    allocations = {
        "US": 33,
        "EU": 33,
        "UK": 34,
    }

    if Path(REGIME_FILE).exists():

        regime = pd.read_csv(REGIME_FILE)

        for _, row in regime.iterrows():

            market = str(row["Market"]).upper()
            state = str(row["Regime"]).upper()

            if state == "BULL":
                allocations[market] += 10

            elif state == "WEAK":
                allocations[market] -= 10

            elif state == "BEAR":
                allocations[market] -= 15

    if Path(ROTATION_FILE).exists():

        txt = Path(ROTATION_FILE).read_text()

        if "Market Rotation Bias: EUROPE" in txt:
            allocations["EU"] += 15

        elif "Market Rotation Bias: USA" in txt:
            allocations["US"] += 15

        elif "Market Rotation Bias: UK" in txt:
            allocations["UK"] += 15

    total = sum(max(v, 0) for v in allocations.values())

    allocations = {
        k: round(max(v, 0) * 100 / total, 1)
        for k, v in allocations.items()
    }

    df = pd.DataFrame(
        [
            {"Market": k, "Allocation_%": v}
            for k, v in allocations.items()
        ]
    )

    df = df.sort_values(
        "Allocation_%",
        ascending=False
    )

    df.to_csv(
        "global_allocations.csv",
        index=False
    )

    print()
    print("===== GLOBAL PORTFOLIO MANAGER =====")
    print(df.to_string(index=False))
    print()
    print("Salvat: global_allocations.csv")


if __name__ == "__main__":
    main()
