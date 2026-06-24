import pandas as pd
import yfinance as yf
from pathlib import Path

from core.indicators import calculate_rsi
from core.portfolio import get_open_positions
from data.storage import load_portfolio
from utils.logger import log
from core.entry_filter import get_dynamic_min_score_to_buy
from core.allocation import get_allocation_weight
from core.exit_intelligence import get_exit_score, should_exit_position
from core.forecast_risk import get_forecast_multiplier

WATCHLIST_FILE = "watchlist.txt"
OUTPUT_FILE = "watchlist_candidates.csv"
NEWS_SUMMARY_FILE = "news_sentiment_summary.csv"
TOP_N = 60


def get_sp500_tickers():
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        tickers = tables[0]["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
        return tickers
    except Exception:
        return [
            "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","BRK-B",
            "LLY","JPM","V","MA","NFLX","COST","XOM","WMT","PG","JNJ","HD","BAC",
            "ABBV","KO","PM","PLTR","ORCL","CRM","CSCO","AMD","ADBE","QCOM","TXN",
            "AMAT","GE","CAT","IBM","NOW","UBER","PANW","CRWD","MU","INTC","SHOP",
            "SNOW","MSTR","COIN","GS","MRK","UNH","DIA","QQQ","SPY"
        ]


def get_news_adjustment(ticker):
    path = Path(NEWS_SUMMARY_FILE)

    if not path.exists():
        return 0, "UNKNOWN"

    try:
        df = pd.read_csv(path)
        row = df[df["Ticker"].astype(str).str.upper() == str(ticker).upper()]

        if row.empty:
            return 0, "UNKNOWN"

        bias = str(row.iloc[0].get("News_Bias", "NEUTRAL")).upper()

        if bias == "POSITIVE":
            return 5, bias

        if bias == "NEGATIVE":
            return -10, bias

        return 0, bias

    except Exception:
        return 0, "UNKNOWN"



def score_ticker(ticker):
    try:
        data = yf.download(ticker, period="6mo", interval="1d", auto_adjust=False, progress=False)
        if data.empty or len(data) < 60:
            return None

        if len(data.columns.names) > 1:
            data.columns = data.columns.droplevel(1)

        close = data["Close"]
        volume = data["Volume"]

        price = float(close.iloc[-1])
        sma20 = float(close.rolling(20).mean().iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])
        rsi = float(calculate_rsi(close).iloc[-1])
        vol = float(volume.iloc[-1])
        avg_vol20 = float(volume.rolling(20).mean().iloc[-1])
        breakout20 = price >= float(close.rolling(20).max().iloc[-2])

        score = 0
        if price > sma20:
            score += 20
        if sma20 > sma50:
            score += 25
        if 45 <= rsi <= 70:
            score += 20
        if vol >= avg_vol20:
            score += 15
        if breakout20:
            score += 20

        news_adjustment, news_bias = get_news_adjustment(ticker)
        technical_score = score
        score = max(0, min(120, score + news_adjustment))

        dynamic_min_score = get_dynamic_min_score_to_buy()
        allocation_weight = get_allocation_weight(score)

        signal = "STRONG BUY" if score >= dynamic_min_score else "WAIT"

        if news_bias == "NEGATIVE" and score < 95:
            signal = "WAIT"

        if signal != "STRONG BUY":
            allocation_weight = 0

        forecast_multiplier = get_forecast_multiplier()
        exit_score = get_exit_score(score, news_bias, forecast_multiplier)
        exit_warning = should_exit_position(score, news_bias, forecast_multiplier)

        return {
            "Ticker": ticker,
            "Price": round(price, 2),
            "Technical_Score": technical_score,
            "News_Bias": news_bias,
            "News_Adjustment": news_adjustment,
            "Dynamic_Min_Score": dynamic_min_score,
            "Allocation_Weight": allocation_weight,
            "Exit_Score": exit_score,
            "Exit_Warning": exit_warning,
            "Exit_Score": exit_score,
            "Exit_Warning": exit_warning,
            "SMA20": round(sma20, 2),
            "SMA50": round(sma50, 2),
            "RSI": round(rsi, 2),
            "Volume": int(vol),
            "Avg_Volume_20": int(avg_vol20),
            "Breakout_20": bool(breakout20),
            "Score": score,
            "Signal": signal,
        }

    except Exception:
        return None


def run_market_scanner(top_n=TOP_N, write_watchlist=True):
    portfolio = load_portfolio()
    held = set(get_open_positions(portfolio).keys()) if not portfolio.empty else set()

    tickers = get_sp500_tickers()
    rows = []

    log(f"Market Scanner: scanez {len(tickers)} tickere...")

    for idx, ticker in enumerate(tickers, 1):
        result = score_ticker(ticker)
        if result:
            result["Held"] = result["Ticker"] in held
            rows.append(result)

        if idx % 50 == 0:
            log(f"Market Scanner: scanate {idx}/{len(tickers)}")

    df = pd.DataFrame(rows)
    if df.empty:
        log("Market Scanner: nu am generat candidați.")
        return df

    df = df.sort_values(["Score", "RSI"], ascending=[False, False])
    df.to_csv(OUTPUT_FILE, index=False)

    selected = df.head(top_n)["Ticker"].tolist()

    if write_watchlist:
        Path(WATCHLIST_FILE).write_text("\n".join(selected) + "\n")
        log(f"Market Scanner: watchlist.txt actualizat cu top {len(selected)} tickere.")

    strong_buy_count = int((df["Signal"] == "STRONG BUY").sum())
    eligible_count = int(((df["Signal"] == "STRONG BUY") & (~df["Held"])).sum())

    log(
        f"Market Scanner: candidați {len(df)} | "
        f"STRONG BUY {strong_buy_count} | eligibili noi {eligible_count}"
    )

    return df


def main():
    df = run_market_scanner()

    if df is not None and not df.empty:
        print(df.head(20)[["Ticker", "Score", "Signal", "Held", "Price"]])


if __name__ == "__main__":
    main()
