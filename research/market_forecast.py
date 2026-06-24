from pathlib import Path
import pandas as pd


def load_risk_mode():
    path = Path("historical_pattern_summary.txt")

    if not path.exists():
        return "NORMAL"

    for line in path.read_text().splitlines():
        if line.startswith("Risk Mode:"):
            return line.split(":", 1)[1].strip()

    return "NORMAL"


def load_news_bias():
    path = Path("news_sentiment_summary.csv")

    if not path.exists():
        return 0

    df = pd.read_csv(path)

    positive = (df["News_Bias"] == "POSITIVE").sum()
    negative = (df["News_Bias"] == "NEGATIVE").sum()

    return positive - negative


def load_historical_forward_stats():
    path = Path("historical_patterns.csv")

    if not path.exists():
        return {}

    df = pd.read_csv(path)
    stats = {}

    mapping = {
        "21d": "Forward_21d_%",
        "63d": "Forward_63d_%",
        "126d": "Forward_126d_%",
        "252d": "Forward_252d_%",
    }

    for horizon, col in mapping.items():
        if col not in df.columns:
            continue

        values = pd.to_numeric(df[col], errors="coerce").dropna()

        if values.empty:
            continue

        stats[horizon] = {
            "avg": float(values.mean()),
            "median": float(values.median()),
            "best": float(values.max()),
            "worst": float(values.min()),
        }

    return stats


def classify_from_return(median_return):
    if median_return >= 5:
        return "BULLISH", 70
    if median_return >= 1:
        return "SLIGHT_BULLISH", 60
    if median_return <= -5:
        return "BEARISH", 70
    if median_return <= -1:
        return "SLIGHT_BEARISH", 60
    return "NEUTRAL", 55

def forecast():
    risk_mode = load_risk_mode()
    news_score = load_news_bias()
    historical_stats = load_historical_forward_stats()

    forecasts = {}

    for horizon in ["21d", "63d", "126d", "252d"]:
        if horizon in historical_stats:
            median_return = historical_stats[horizon]["median"]
            forecasts[horizon] = classify_from_return(median_return)
        else:
            forecasts[horizon] = ("NEUTRAL", 55)

    if news_score > 5:
        forecasts["21d"] = ("BULLISH", max(forecasts["21d"][1], 65))
        forecasts["63d"] = ("BULLISH", max(forecasts["63d"][1], 60))

    if risk_mode == "CAUTIOUS":
        if forecasts["126d"][0] in ["NEUTRAL", "SLIGHT_BULLISH"]:
            forecasts["126d"] = ("SLIGHT_BEARISH", 60)
        if forecasts["252d"][0] in ["NEUTRAL", "SLIGHT_BULLISH"]:
            forecasts["252d"] = ("SLIGHT_BEARISH", 60)

    return forecasts


def export_forecast(forecasts):
    rows = []

    for horizon, (view, confidence) in forecasts.items():
        rows.append({
            "Horizon": horizon,
            "Forecast": view,
            "Confidence_%": confidence,
        })

    df = pd.DataFrame(rows)
    df.to_csv("market_forecast.csv", index=False)

    lines = ["Market Forecast Summary", "======================="]

    for row in rows:
        lines.append(f"{row['Horizon']}: {row['Forecast']} ({row['Confidence_%']}%)")

    Path("market_forecast_summary.txt").write_text("\n".join(lines))

def main():
    forecasts = forecast()
    export_forecast(forecasts)

    print("\n===== MARKET FORECAST ENGINE =====\n")

    for horizon, (view, confidence) in forecasts.items():
        print(f"{horizon:>4} -> {view:<8} ({confidence}%)")


if __name__ == "__main__":
    main()
