import pandas as pd
from pathlib import Path

from markets.market_config import MARKETS
from markets.market_hours import is_market_open
from research.market_scanner import score_ticker


def load_watchlist(path):
    p = Path(path)

    if not p.exists():
        return []

    return [
        x.strip().upper()
        for x in p.read_text().splitlines()
        if x.strip()
    ]


def main():
    rows = []

    for market_name, cfg in MARKETS.items():

        if not cfg.get("enabled", False):
            continue

        tickers = load_watchlist(cfg["watchlist"])

        print(
            f"{market_name}: {len(tickers)} tickere"
        )

        for ticker in tickers:
            try:
                result = score_ticker(ticker)

                if not result:
                    continue

                result["Market"] = market_name
                result["Market_Open"] = is_market_open(market_name)

                rows.append(result)

            except Exception:
                pass

    if not rows:
        print("Nu am găsit candidați.")
        return

    df = pd.DataFrame(rows)

    df = df.sort_values(
        "Score",
        ascending=False
    )

    df.to_csv(
        "multi_market_candidates.csv",
        index=False
    )

    print()
    print(
        df[
            [
                "Market",
                "Ticker",
                "Score",
                "Signal",
                "Market_Open"
            ]
        ].head(20)
    )

    print()
    print(
        "Salvat: multi_market_candidates.csv"
    )


if __name__ == "__main__":
    main()
