import pandas as pd
import yfinance as yf
from pathlib import Path

FORWARD_WINDOWS = [21, 63, 126, 252]


def load_spy(period="20y"):
    data = yf.download("SPY", period=period, auto_adjust=True, progress=False)

    if data.empty:
        raise RuntimeError("Nu am putut descărca date SPY.")

    if len(data.columns.names) > 1:
        data.columns = data.columns.droplevel(1)

    data = data[["Close", "Volume"]].copy()
    data["Return_20d"] = data["Close"].pct_change(20) * 100
    data["Return_60d"] = data["Close"].pct_change(60) * 100
    data["Volatility_60d"] = data["Close"].pct_change().rolling(60).std() * (252 ** 0.5) * 100
    data["SMA200"] = data["Close"].rolling(200).mean()
    data["Distance_SMA200_%"] = ((data["Close"] - data["SMA200"]) / data["SMA200"]) * 100
    data["Drawdown_%"] = ((data["Close"] / data["Close"].cummax()) - 1) * 100

    return data.dropna()


def feature_vector(row):
    return {
        "Return_20d": float(row["Return_20d"]),
        "Return_60d": float(row["Return_60d"]),
        "Volatility_60d": float(row["Volatility_60d"]),
        "Distance_SMA200_%": float(row["Distance_SMA200_%"]),
        "Drawdown_%": float(row["Drawdown_%"]),
    }


def similarity_score(current, past):
    weights = {
        "Return_20d": 1.0,
        "Return_60d": 1.0,
        "Volatility_60d": 1.2,
        "Distance_SMA200_%": 1.5,
        "Drawdown_%": 1.5,
    }

    scale = {
        "Return_20d": 10,
        "Return_60d": 20,
        "Volatility_60d": 20,
        "Distance_SMA200_%": 20,
        "Drawdown_%": 30,
    }

    distance = 0.0

    for key in weights:
        diff = abs(current[key] - past[key]) / scale[key]
        distance += diff * weights[key]

    return round(max(0, 100 - distance * 25), 2)


def forward_return(data, idx, days):
    pos = data.index.get_loc(idx)
    future_pos = pos + days

    if future_pos >= len(data):
        return None

    current_price = float(data.iloc[pos]["Close"])
    future_price = float(data.iloc[future_pos]["Close"])

    return round(((future_price / current_price) - 1) * 100, 2)


def find_historical_patterns(top_n=10):
    data = load_spy("20y")
    current = feature_vector(data.iloc[-1])

    rows = []
    max_forward = max(FORWARD_WINDOWS)

    for idx in data.index[:-max_forward]:
        past = feature_vector(data.loc[idx])
        sim = similarity_score(current, past)

        if sim < 60:
            continue

        row = data.loc[idx]

        result = {
            "Date": idx.strftime("%Y-%m-%d"),
            "Similarity_%": sim,
            "Close": round(float(row["Close"]), 2),
            "Return_20d": round(float(row["Return_20d"]), 2),
            "Return_60d": round(float(row["Return_60d"]), 2),
            "Volatility_60d": round(float(row["Volatility_60d"]), 2),
            "Distance_SMA200_%": round(float(row["Distance_SMA200_%"]), 2),
            "Drawdown_%": round(float(row["Drawdown_%"]), 2),
        }

        for days in FORWARD_WINDOWS:
            result[f"Forward_{days}d_%"] = forward_return(data, idx, days)

        rows.append(result)

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    return df.sort_values("Similarity_%", ascending=False).head(top_n)


def export_summary(df):
    if df.empty:
        Path("historical_pattern_summary.txt").write_text("NO_PATTERNS_FOUND")
        return

    summary = []

    summary.append("Historical Pattern Summary")
    summary.append("==========================")
    summary.append(f"Top Similarity: {df.iloc[0]['Similarity_%']}% on {df.iloc[0]['Date']}")

    for days in FORWARD_WINDOWS:
        col = f"Forward_{days}d_%"
        valid = pd.to_numeric(df[col], errors="coerce").dropna()

        if not valid.empty:
            summary.append(
                f"{days}d avg={valid.mean():.2f}% median={valid.median():.2f}% "
                f"best={valid.max():.2f}% worst={valid.min():.2f}%"
            )

    median_126 = pd.to_numeric(df["Forward_126d_%"], errors="coerce").dropna().median()
    median_252 = pd.to_numeric(df["Forward_252d_%"], errors="coerce").dropna().median()

    if median_126 < -5 or median_252 < -5:
        risk_mode = "CAUTIOUS"
    elif median_126 > 5 and median_252 > 5:
        risk_mode = "AGGRESSIVE"
    else:
        risk_mode = "NORMAL"

    summary.append(f"Risk Mode: {risk_mode}")

    Path("historical_pattern_summary.txt").write_text("\n".join(summary))

def main():
    df = find_historical_patterns(top_n=10)
    df.to_csv("historical_patterns.csv", index=False)
    export_summary(df)

    if df.empty:
        print("Nu am găsit perioade istorice similare.")
        return

    print()
    print("===== HISTORICAL PATTERN ENGINE =====")
    print(df.to_string(index=False))

    print()
    print("===== FORWARD RETURNS FROM SIMILAR PERIODS =====")

    for days in FORWARD_WINDOWS:
        col = f"Forward_{days}d_%"
        valid = pd.to_numeric(df[col], errors="coerce").dropna()

        print(
            f"{days:>3} zile: "
            f"medie {valid.mean():>6.2f}% | "
            f"mediană {valid.median():>6.2f}% | "
            f"best {valid.max():>6.2f}% | "
            f"worst {valid.min():>6.2f}%"
        )


if __name__ == "__main__":
    main()
