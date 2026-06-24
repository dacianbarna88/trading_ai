import pandas as pd
from pathlib import Path

FILE = "learning_weight_history.csv"


def calculate_weight(accuracy):

    if accuracy >= 80:
        return 2.0

    if accuracy >= 70:
        return 1.5

    if accuracy >= 60:
        return 1.2

    if accuracy >= 50:
        return 1.0

    if accuracy >= 40:
        return 0.8

    return 0.6


def update_weights():

    if not Path(FILE).exists():
        print("learning_weight_history.csv missing")
        return

    df = pd.read_csv(FILE)

    latest = (
        df.sort_values("Timestamp")
          .groupby("Vote")
          .tail(1)
          .copy()
    )

    latest["New_Weight"] = (
        latest["Accuracy_%"]
        .fillna(0)
        .apply(calculate_weight)
    )

    print("\n===== V27.6 ADAPTIVE WEIGHTS =====\n")

    for _, row in latest.iterrows():
        print(
            f"{row['Vote']} | "
            f"Accuracy {row['Accuracy_%']}% | "
            f"Weight {row['New_Weight']}"
        )

    latest.to_csv(
        "adaptive_weights.csv",
        index=False
    )

    print("\nadaptive_weights.csv updated")


if __name__ == "__main__":
    update_weights()
