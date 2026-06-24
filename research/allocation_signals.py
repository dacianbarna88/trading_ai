import pandas as pd
from pathlib import Path

INPUT_FILE = "safe_migration_plan.csv"
OUTPUT_FILE = "allocation_signals.csv"
SUMMARY_FILE = "allocation_signals_summary.txt"


def main():
    if not Path(INPUT_FILE).exists():
        print("Lipsește safe_migration_plan.csv")
        return

    df = pd.read_csv(INPUT_FILE)

    signals = []

    for _, row in df.iterrows():
        action = str(row["Action"]).upper()
        ticker = str(row["Ticker"])
        amount = float(row["Amount_$"])
        market = str(row.get("Market", ""))

        signal = "WAIT"

        if action == "SELL":
            signal = "ALLOCATOR_SELL"

        if action == "BUY":
            signal = "ALLOCATOR_BUY"

        signals.append({
            "Ticker": ticker,
            "Market": market,
            "Signal": signal,
            "Amount_$": round(amount, 2),
            "Source": "V8_GLOBAL_ALLOCATOR",
            "Status": "PAPER_ONLY",
        })

    out = pd.DataFrame(signals)
    out.to_csv(OUTPUT_FILE, index=False)

    lines = [
        "Allocation Signals Summary",
        "==========================",
        "",
        f"Total Signals: {len(out)}",
        f"BUY Signals: {(out['Signal'] == 'ALLOCATOR_BUY').sum()}",
        f"SELL Signals: {(out['Signal'] == 'ALLOCATOR_SELL').sum()}",
        "",
        out.to_string(index=False),
    ]

    Path(SUMMARY_FILE).write_text("\n".join(lines))

    print("\n".join(lines))


if __name__ == "__main__":
    main()
