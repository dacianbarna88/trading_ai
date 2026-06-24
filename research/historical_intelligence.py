import yfinance as yf
import pandas as pd

MARKETS = {
    "US": "SPY",
    "EU": "VGK",
    "UK": "EWU",
}


def calc_return(data, years):
    days = years * 252

    if len(data) < days:
        return None

    start = float(data["Close"].iloc[-days])
    end = float(data["Close"].iloc[-1])

    if start <= 0:
        return None

    return round(((end / start) - 1) * 100, 2)


def classify_bull_probability(r2, r5, r10):
    score = 50

    for r in [r2, r5, r10]:
        if r is None:
            continue

        if r > 50:
            score += 15
        elif r > 20:
            score += 10
        elif r > 0:
            score += 5
        else:
            score -= 10

    return max(0, min(100, score))


def classify_regime(prob):
    if prob >= 75:
        return "LONG_TERM_BULL"
    if prob >= 60:
        return "NEUTRAL_BULL"
    if prob >= 45:
        return "MIXED"
    return "WEAK"


def main():
    rows = []

    for market, ticker in MARKETS.items():
        data = yf.download(
            ticker,
            period="10y",
            auto_adjust=False,
            progress=False,
        )

        if data.empty:
            rows.append({
                "Market": market,
                "Ticker": ticker,
                "Return_2Y_%": None,
                "Return_5Y_%": None,
                "Return_10Y_%": None,
                "Bull_Probability": 50,
                "Regime": "UNKNOWN",
            })
            continue

        if len(data.columns.names) > 1:
            data.columns = data.columns.droplevel(1)

        r2 = calc_return(data, 2)
        r5 = calc_return(data, 5)
        r10 = calc_return(data, 10)

        prob = classify_bull_probability(r2, r5, r10)

        rows.append({
            "Market": market,
            "Ticker": ticker,
            "Return_2Y_%": r2,
            "Return_5Y_%": r5,
            "Return_10Y_%": r10,
            "Bull_Probability": prob,
            "Regime": classify_regime(prob),
        })

    df = pd.DataFrame(rows)
    df.to_csv("historical_intelligence.csv", index=False)

    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
