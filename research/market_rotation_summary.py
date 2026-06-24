from pathlib import Path
import pandas as pd

INPUT_FILE = "market_rotation.csv"


def main():
    path = Path(INPUT_FILE)

    if not path.exists():
        print("Lipsește market_rotation.csv")
        return

    df = pd.read_csv(path)

    leaders = df.head(3)["Sector"].tolist()
    laggards = df.tail(3)["Sector"].tolist()

    europe_score = (
        df[df["Sector"].str.startswith("EU")]["Score"].mean()
        if not df[df["Sector"].str.startswith("EU")].empty
        else 0
    )

    us_score = (
        df[df["Sector"].str.startswith("US")]["Score"].mean()
        if not df[df["Sector"].str.startswith("US")].empty
        else 0
    )

    uk_score = (
        df[df["Sector"].str.startswith("UK")]["Score"].mean()
        if not df[df["Sector"].str.startswith("UK")].empty
        else 0
    )

    scores = {
        "EUROPE": europe_score,
        "USA": us_score,
        "UK": uk_score,
    }

    bias = max(scores, key=scores.get)

    lines = [
        "Market Rotation Summary",
        "=======================",
        "",
        "LEADERS:",
        *leaders,
        "",
        "LAGGARDS:",
        *laggards,
        "",
        f"Europe Score: {europe_score:.1f}",
        f"USA Score: {us_score:.1f}",
        f"UK Score: {uk_score:.1f}",
        "",
        f"Market Rotation Bias: {bias}",
    ]

    Path("market_rotation_summary.txt").write_text(
        "\n".join(lines)
    )

    print("\n".join(lines))


if __name__ == "__main__":
    main()
