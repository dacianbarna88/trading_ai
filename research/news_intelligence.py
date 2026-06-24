import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path

WATCHLIST_FILE = "watchlist.txt"
OUTPUT_FILE = "news_intelligence.csv"

POSITIVE_WORDS = [
    "beat", "beats", "growth", "upgrade", "strong", "record", "surge",
    "rally", "profit", "optimistic", "raises", "outperform", "buy"
]

NEGATIVE_WORDS = [
    "miss", "misses", "downgrade", "weak", "loss", "falls", "drop",
    "lawsuit", "probe", "warning", "cuts", "underperform", "sell"
]


def load_watchlist():
    path = Path(WATCHLIST_FILE)
    if not path.exists():
        return []

    return [x.strip().upper() for x in path.read_text().splitlines() if x.strip()]


def score_text(text):
    text = str(text).lower()
    positive = sum(1 for word in POSITIVE_WORDS if word in text)
    negative = sum(1 for word in NEGATIVE_WORDS if word in text)
    return positive - negative


def classify_sentiment(score):
    if score > 0:
        return "POSITIVE"
    if score < 0:
        return "NEGATIVE"
    return "NEUTRAL"


def normalize_news_item(item):
    content = item.get("content", {}) if isinstance(item, dict) else {}

    title = item.get("title") or content.get("title") or ""
    publisher = item.get("publisher") or content.get("provider", {}).get("displayName", "")
    link = item.get("link") or content.get("canonicalUrl", {}).get("url", "")

    ts = item.get("providerPublishTime") or content.get("pubDate")
    published = ""

    if isinstance(ts, (int, float)):
        published = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(ts, str):
        published = ts

    return str(title).strip(), str(publisher).strip(), str(link).strip(), published


def get_ticker_news(ticker, limit=5):
    rows = []

    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []

        valid_count = 0

        for item in news:
            title, publisher, link, published = normalize_news_item(item)

            if not title:
                continue

            score = score_text(title)

            rows.append({
                "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": ticker,
                "Published": published,
                "Publisher": publisher,
                "Title": title,
                "Sentiment_Score": score,
                "Sentiment": classify_sentiment(score),
                "Link": link,
            })

            valid_count += 1

            if valid_count >= limit:
                break

        if valid_count == 0:
            rows.append({
                "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": ticker,
                "Published": "",
                "Publisher": "",
                "Title": "NO_NEWS",
                "Sentiment_Score": 0,
                "Sentiment": "NEUTRAL",
                "Link": "",
            })

    except Exception as e:
        rows.append({
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Ticker": ticker,
            "Published": "",
            "Publisher": "",
            "Title": f"NEWS_ERROR: {e}",
            "Sentiment_Score": 0,
            "Sentiment": "UNKNOWN",
            "Link": "",
        })

    return rows


def run_news_intelligence(max_tickers=30, news_per_ticker=5):
    tickers = load_watchlist()[:max_tickers]
    all_rows = []

    print(f"News Intelligence: verific {len(tickers)} tickere...")

    for ticker in tickers:
        all_rows.extend(get_ticker_news(ticker, news_per_ticker))

    df = pd.DataFrame(all_rows)
    df.to_csv(OUTPUT_FILE, index=False)

    if df.empty:
        print("Nu am găsit știri.")
        return df

    summary = (
        df.groupby(["Ticker", "Sentiment"])
        .size()
        .reset_index(name="Count")
        .sort_values(["Ticker", "Count"], ascending=[True, False])
    )

    print()
    print("===== NEWS INTELLIGENCE SUMMARY =====")
    print(summary.to_string(index=False))
    print()
    print(f"Salvat: {OUTPUT_FILE}")

    return df


if __name__ == "__main__":
    run_news_intelligence()
