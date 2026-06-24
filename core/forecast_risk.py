from pathlib import Path
import pandas as pd

FORECAST_FILE = "market_forecast.csv"

def get_forecast_multiplier():
    path = Path(FORECAST_FILE)

    if not path.exists():
        return 1.0

    try:
        df = pd.read_csv(path)

        score = 0

        for _, row in df.iterrows():
            view = str(row["Forecast"]).upper()

            if "BULLISH" in view:
                score += 1

            if "BEARISH" in view:
                score -= 1

        if score >= 3:
            return 1.25

        if score >= 1:
            return 1.0

        if score <= -3:
            return 0.5

        return 0.75

    except Exception:
        return 1.0


if __name__ == "__main__":
    print("Forecast Multiplier:", get_forecast_multiplier())
