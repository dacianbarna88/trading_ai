import yfinance as yf
import pandas as pd


def max_drawdown(series):
    rolling_max = series.cummax()
    drawdown = (series - rolling_max) / rolling_max
    return float(drawdown.min() * 100)


def analyze_period(years):
    data = yf.download(
        "SPY",
        period=f"{years}y",
        auto_adjust=True,
        progress=False,
    )

    if data.empty:
        return None

    if len(data.columns.names) > 1:
        data.columns = data.columns.droplevel(1)

    close = data["Close"]

    total_return = ((close.iloc[-1] / close.iloc[0]) - 1) * 100
    daily_returns = close.pct_change().dropna()
    volatility = daily_returns.std() * (252 ** 0.5) * 100
    mdd = max_drawdown(close)

    sma200 = close.rolling(200).mean()
    bull_days = int((close > sma200).sum())
    bear_days = int((close < sma200).sum())

    return {
        "Years": years,
        "Return_%": round(float(total_return), 2),
        "Volatility_%": round(float(volatility), 2),
        "Max_Drawdown_%": round(float(mdd), 2),
        "Bull_Days": bull_days,
        "Bear_Days": bear_days,
    }


def main():
    results = []

    for years in [2, 5, 10, 20]:
        r = analyze_period(years)
        if r:
            results.append(r)

    df = pd.DataFrame(results)

    print()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
