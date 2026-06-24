import yfinance as yf
import pandas as pd
from pathlib import Path

MARKETS = {
    "US_LARGE_CAP": "SPY",
    "US_TECH": "QQQ",
    "US_BLUE_CHIP": "DIA",
    "US_SMALL_CAP": "IWM",
    "EUROPE": "VGK",
    "EUROZONE": "FEZ",
    "UK": "EWU",
    "JAPAN": "EWJ",
    "HONG_KONG": "EWH",
    "INDIA": "INDA",
}

PERIODS = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "12M": "1y",
}

results = []

for name, ticker in MARKETS.items():
    row = {
        "Market": name,
        "Ticker": ticker,
    }

    for label, period in PERIODS.items():
        try:
            data = yf.download(
                ticker,
                period=period,
                progress=False,
                auto_adjust=True
            )

            if data.empty:
                row[f"Return_{label}_%"] = 0
                continue

            close = data["Close"]

            if isinstance(close, pd.DataFrame):
                close = close[ticker]

            close = close.dropna()

            if close.empty:
                row[f"Return_{label}_%"] = 0
                continue

            start = float(close.iloc[0])
            end = float(close.iloc[-1])

            ret = round(((end - start) / start) * 100, 2)
            row[f"Return_{label}_%"] = ret

        except Exception:
            row[f"Return_{label}_%"] = 0

    results.append(row)

df = pd.DataFrame(results)

df["Strategic_Score"] = (
    df["Return_1M_%"] * 0.40 +
    df["Return_3M_%"] * 0.30 +
    df["Return_6M_%"] * 0.20 +
    df["Return_12M_%"] * 0.10
).round(2)

df = df.sort_values(
    by="Strategic_Score",
    ascending=False
)

df.to_csv(
    "global_market_scanner.csv",
    index=False
)

leader = df.iloc[0]

summary = [
    "===== V16.1 GLOBAL MARKET SCANNER =====",
    "",
    f"Strategic Leader: {leader['Market']} ({leader['Ticker']})",
    f"Strategic Score: {leader['Strategic_Score']}",
    "",
    "Market Ranking:",
]

for _, r in df.iterrows():
    summary.append(
        f"{r['Market']} | {r['Ticker']} | "
        f"1M {r['Return_1M_%']}% | "
        f"3M {r['Return_3M_%']}% | "
        f"6M {r['Return_6M_%']}% | "
        f"12M {r['Return_12M_%']}% | "
        f"Score {r['Strategic_Score']}"
    )

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path("global_market_scanner_summary.txt").write_text(text)

print(text)
