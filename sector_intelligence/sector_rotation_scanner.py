import yfinance as yf
import pandas as pd
from pathlib import Path

SECTORS = {
    "TECHNOLOGY": "XLK",
    "FINANCIALS": "XLF",
    "HEALTHCARE": "XLV",
    "ENERGY": "XLE",
    "INDUSTRIALS": "XLI",
    "CONSUMER_DISCRETIONARY": "XLY",
    "CONSUMER_STAPLES": "XLP",
    "UTILITIES": "XLU",
    "REAL_ESTATE": "XLRE",
    "MATERIALS": "XLB",
    "COMMUNICATIONS": "XLC",
}

PERIODS = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "12M": "1y",
}

rows = []

for sector, ticker in SECTORS.items():
    row = {"Sector": sector, "Ticker": ticker}

    for label, period in PERIODS.items():
        try:
            data = yf.download(
                ticker,
                period=period,
                progress=False,
                auto_adjust=True
            )

            close = data["Close"]

            if isinstance(close, pd.DataFrame):
                close = close[ticker]

            close = close.dropna()

            if close.empty:
                row[f"Return_{label}_%"] = 0
                continue

            start = float(close.iloc[0])
            end = float(close.iloc[-1])

            row[f"Return_{label}_%"] = round(
                ((end - start) / start) * 100,
                2
            )

        except Exception:
            row[f"Return_{label}_%"] = 0

    rows.append(row)

df = pd.DataFrame(rows)

df["Sector_Score"] = (
    df["Return_1M_%"] * 0.40 +
    df["Return_3M_%"] * 0.30 +
    df["Return_6M_%"] * 0.20 +
    df["Return_12M_%"] * 0.10
).round(2)

df = df.sort_values("Sector_Score", ascending=False)

df.to_csv("sector_rotation.csv", index=False)

leader = df.iloc[0]

summary = [
    "===== V17.0 SECTOR ROTATION SCANNER =====",
    "",
    f"Sector Leader: {leader['Sector']} ({leader['Ticker']})",
    f"Sector Score: {leader['Sector_Score']}",
    "",
    "Sector Ranking:",
]

for _, r in df.iterrows():
    summary.append(
        f"{r['Sector']} | {r['Ticker']} | "
        f"1M {r['Return_1M_%']}% | "
        f"3M {r['Return_3M_%']}% | "
        f"6M {r['Return_6M_%']}% | "
        f"12M {r['Return_12M_%']}% | "
        f"Score {r['Sector_Score']}"
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

Path("sector_rotation_summary.txt").write_text(text)

print(text)
