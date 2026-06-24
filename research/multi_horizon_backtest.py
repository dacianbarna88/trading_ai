import pandas as pd
import yfinance as yf

markets = {
    "US": "SPY",
    "EU": "VGK",
    "UK": "EWU"
}

periods = {
    "2Y": "2y",
    "5Y": "5y",
    "10Y": "10y"
}

rows = []

for market, ticker in markets.items():

    row = {
        "Market": market,
        "Ticker": ticker
    }

    for label, period in periods.items():

        try:

            df = yf.download(
                ticker,
                period=period,
                auto_adjust=True,
                progress=False
            )

            close = df["Close"]

            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]

            start_price = float(close.iloc[0])
            end_price = float(close.iloc[-1])

            ret = round(
                ((end_price / start_price) - 1) * 100,
                2
            )

            row[f"Return_{label}_%"] = ret

        except:
            row[f"Return_{label}_%"] = None

    rows.append(row)

out = pd.DataFrame(rows)

out.to_csv(
    "multi_horizon_backtest.csv",
    index=False
)

print("\n===== MULTI HORIZON BACKTEST =====\n")
print(out.to_string(index=False))
