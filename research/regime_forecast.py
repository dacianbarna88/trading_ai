from pathlib import Path
import pandas as pd


def load_market_forecast():
    path = Path("market_forecast.csv")
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    return dict(zip(df["Horizon"], df["Forecast"]))


def load_historical_risk():
    path = Path("historical_pattern_summary.txt")
    if not path.exists():
        return "NORMAL"

    for line in path.read_text().splitlines():
        if line.startswith("Risk Mode:"):
            return line.split(":", 1)[1].strip().upper()

    return "NORMAL"


def forecast_regime():
    forecast = load_market_forecast()
    risk = load_historical_risk()

    short = forecast.get("21d", "NEUTRAL")
    medium = forecast.get("126d", "NEUTRAL")
    long = forecast.get("252d", "NEUTRAL")

    if risk == "CAUTIOUS" and "BEARISH" in medium and "BEARISH" in long:
        regime = "BULL_RISK_EXHAUSTION"
        confidence = 70
    elif "BULLISH" in short and risk in ["NORMAL", "AGGRESSIVE"]:
        regime = "BULL_EXPANSION"
        confidence = 65
    elif "BEARISH" in medium and "BEARISH" in long:
        regime = "BEAR_RISK"
        confidence = 70
    else:
        regime = "MIXED_NEUTRAL"
        confidence = 55

    return {
        "Regime_Forecast": regime,
        "Confidence_%": confidence,
        "Historical_Risk": risk,
        "Short_Term": short,
        "Medium_Term": medium,
        "Long_Term": long,
    }


def main():
    result = forecast_regime()

    df = pd.DataFrame([result])
    df.to_csv("regime_forecast.csv", index=False)

    lines = [
        "Regime Forecast Summary",
        "=======================",
        f"Regime Forecast: {result['Regime_Forecast']}",
        f"Confidence: {result['Confidence_%']}%",
        f"Historical Risk: {result['Historical_Risk']}",
        f"Short Term: {result['Short_Term']}",
        f"Medium Term: {result['Medium_Term']}",
        f"Long Term: {result['Long_Term']}",
    ]

    Path("regime_forecast_summary.txt").write_text("\n".join(lines))

    print("\n".join(lines))


if __name__ == "__main__":
    main()
