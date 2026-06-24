import yfinance as yf
import pandas as pd


MARKETS = ["SPY", "QQQ", "DIA", "IWM"]


def get_close_series(data, ticker):
    close = data["Close"]

    if isinstance(close, pd.DataFrame):
        close = close[ticker]

    return close.dropna()


def analyze_2y():
    results = []

    for ticker in MARKETS:
        try:
            data = yf.download(
                ticker,
                period="2y",
                progress=False,
                auto_adjust=True
            )

            close = get_close_series(data, ticker)

            if len(close) < 2:
                continue

            start_price = float(close.iloc[0])
            end_price = float(close.iloc[-1])

            total_return = ((end_price - start_price) / start_price) * 100

            results.append({
                "Market": ticker,
                "Return_%": round(total_return, 2)
            })

        except Exception as e:
            print(f"{ticker} ERROR: {e}")

    if not results:
        return None

    df = pd.DataFrame(results)

    return df.sort_values("Return_%", ascending=False).iloc[0].to_dict()


if __name__ == "__main__":
    print("\n===== 2Y HORIZON =====\n")
    print(analyze_2y())
