from pathlib import Path
from datetime import datetime

import pandas as pd
import yfinance as yf

WATCHLIST_FILE = "watchlist.txt"
WATCHLIST_BACKUP_FILE = "watchlist_backup.txt"
CANDIDATES_FILE = "watchlist_candidates.csv"

MAX_TICKERS = 20
MIN_PRICE = 10
MIN_AVG_VOLUME = 1_000_000

CANDIDATES = [
    "AAPL", "MSFT", "NVDA", "AMD", "AVGO", "META", "GOOGL", "AMZN", "TSLA", "NFLX",
    "CRM", "ORCL", "ADBE", "NOW", "PANW", "CRWD", "PLTR", "SNOW", "SHOP", "UBER",
    "JPM", "BAC", "GS", "V", "MA", "AXP",
    "UNH", "LLY", "NVO", "ABBV", "MRK", "TMO",
    "COST", "WMT", "HD", "MCD", "NKE",
    "SPY", "QQQ", "IWM", "DIA"
]


def score_ticker(ticker):
    try:
        data = yf.download(
            ticker,
            period="6mo",
            auto_adjust=False,
            progress=False,
        )

        if data.empty or len(data) < 60:
            return None

        if len(data.columns.names) > 1:
            data.columns = data.columns.droplevel(1)

        close = data["Close"]
        volume = data["Volume"]

        last_price = float(close.iloc[-1])
        avg_volume = float(volume.tail(20).mean())

        if last_price < MIN_PRICE or avg_volume < MIN_AVG_VOLUME:
            return None

        sma20 = float(close.rolling(20).mean().iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])
        high_20 = float(close.tail(20).max())

        ret_5d = (last_price / float(close.iloc[-6]) - 1) * 100
        ret_20d = (last_price / float(close.iloc[-21]) - 1) * 100
        ret_60d = (last_price / float(close.iloc[-61]) - 1) * 100

        score = 0

        if last_price > sma20:
            score += 20
        if last_price > sma50:
            score += 25
        if sma20 > sma50:
            score += 20
        if ret_20d > 0:
            score += 15
        if ret_60d > 0:
            score += 10
        if last_price >= high_20 * 0.97:
            score += 10

        # Penalizare pentru spike prea agresiv pe 5 zile
        if ret_5d > 20:
            score -= 15

        return {
            "Ticker": ticker,
            "Price": round(last_price, 2),
            "Avg_Volume_20d": int(avg_volume),
            "Return_5d_%": round(ret_5d, 2),
            "Return_20d_%": round(ret_20d, 2),
            "Return_60d_%": round(ret_60d, 2),
            "SMA20": round(sma20, 2),
            "SMA50": round(sma50, 2),
            "Score": score,
            "Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    except Exception as e:
        print(f"{ticker}: ERROR {e}")
        return None


def main():
    print(f"Analizez {len(CANDIDATES)} tickere candidate...")

    rows = []

    for ticker in CANDIDATES:
        result = score_ticker(ticker)
        if result is not None:
            rows.append(result)
            print(f"{ticker}: score {result['Score']}")

    if not rows:
        print("Nu am găsit tickere valide. watchlist.txt nu a fost modificat.")
        return

    df = pd.DataFrame(rows).sort_values("Score", ascending=False)
    df.to_csv(CANDIDATES_FILE, index=False)

    selected = df.head(MAX_TICKERS)["Ticker"].tolist()

    watchlist_path = Path(WATCHLIST_FILE)
    backup_path = Path(WATCHLIST_BACKUP_FILE)

    if watchlist_path.exists():
        backup_path.write_text(watchlist_path.read_text(encoding="utf-8"), encoding="utf-8")

    watchlist_path.write_text("\n".join(selected) + "\n", encoding="utf-8")

    print("\n✅ watchlist.txt actualizat cu:")
    for ticker in selected:
        print(ticker)

    print(f"\nBackup salvat în: {WATCHLIST_BACKUP_FILE}")
    print(f"Scoruri salvate în: {CANDIDATES_FILE}")


if __name__ == "__main__":
    main()