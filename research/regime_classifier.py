import pandas as pd
import yfinance as yf


def classify_regime(close, sma200):
    if pd.isna(sma200):
        return "UNKNOWN"

    distance = ((close - sma200) / sma200) * 100

    if distance <= -20:
        return "CRASH"

    if distance < 0:
        return "BEAR"

    if distance < 10:
        return "RECOVERY"

    return "BULL"


def analyze_period(years):
    data = yf.download(
        "SPY",
        period=f"{years}y",
        auto_adjust=True,
        progress=False,
    )

    if len(data.columns.names) > 1:
        data.columns = data.columns.droplevel(1)

    data["SMA200"] = data["Close"].rolling(200).mean()

    data["Regime"] = data.apply(
        lambda r: classify_regime(
            float(r["Close"]),
            float(r["SMA200"]) if pd.notna(r["SMA200"]) else None,
        ),
        axis=1,
    )

    counts = data["Regime"].value_counts()

    total = counts.sum()

    print()
    print(f"===== {years} ANI =====")

    for regime in ["BULL", "RECOVERY", "BEAR", "CRASH"]:
        value = int(counts.get(regime, 0))
        pct = (value / total * 100) if total else 0

        print(
            f"{regime:<10} {value:>5} zile   {pct:>6.2f}%"
        )


def main():
    for years in [2, 5, 10, 20]:
        analyze_period(years)


if __name__ == "__main__":
    main()
