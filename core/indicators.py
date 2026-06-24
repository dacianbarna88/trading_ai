import yfinance as yf


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def get_latest_price(ticker, log=None):
    try:
        data = yf.download(
            ticker,
            period="5d",
            auto_adjust=False,
            progress=False,
        )

        if data.empty:
            return None

        if len(data.columns.names) > 1:
            data.columns = data.columns.droplevel(1)

        return float(data["Close"].iloc[-1])

    except Exception as e:
        if log:
            log(f"Eroare preț live {ticker}: {e}")
        return None
