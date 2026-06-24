import yfinance as yf
import pandas as pd

ticker = "SPY"

data = yf.download(ticker, period="2y", auto_adjust=False)

if len(data.columns.names) > 1:
    data.columns = data.columns.droplevel(1)

results = []

for sma in [20, 50, 100, 200]:
    for rsi_low in [30, 35, 40, 45]:
        for rsi_high in [60, 65, 70, 75]:

            temp = data.copy()

            temp["SMA"] = temp["Close"].rolling(window=sma).mean()

            delta = temp["Close"].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()

            rs = avg_gain / avg_loss
            temp["RSI"] = 100 - (100 / (1 + rs))

            temp["Signal"] = 0
            temp.loc[
                (temp["Close"] > temp["SMA"]) &
                (temp["RSI"] > rsi_low) &
                (temp["RSI"] < rsi_high),
                "Signal"
            ] = 1

            temp["Returns"] = temp["Close"].pct_change()
            temp["Strategy"] = temp["Returns"] * temp["Signal"].shift(1)

            strategy_return = (1 + temp["Strategy"]).cumprod().iloc[-1]

            results.append({
                "SMA": sma,
                "RSI_LOW": rsi_low,
                "RSI_HIGH": rsi_high,
                "Return": round((strategy_return - 1) * 100, 2)
            })

df = pd.DataFrame(results)
df = df.sort_values(by="Return", ascending=False)

print(df.head(10))

df.to_csv("optimization_results.csv", index=False)

print("\nFisier optimization_results.csv salvat!")